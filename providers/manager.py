"""
Blogy — Provider Manager
Intelligent multi-provider LLM manager with:
- Round-robin provider rotation (distributes load across all providers)
- Priority-ordered fallback on failure
- Automatic recovery from rate limits
- Exponential backoff retry
- Per-provider request throttling with dynamic delay
- Health tracking (failure rate, response time, rate limit cooldowns)
- Per-request logging
"""

import os
import time
import logging
from collections import defaultdict
from dotenv import load_dotenv

# Ensure .env is loaded before providers check for API keys
load_dotenv()

from providers.openai_provider import OpenAIProvider
from providers.gemini_provider import GeminiProvider
from providers.groq_provider import GroqProvider
from providers.grok_provider import GrokProvider
from providers.ollama_provider import OllamaProvider

# ── Setup Logging ─────────────────────────────────────────────────────────
logger = logging.getLogger("blogy.providers")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
))
if not logger.handlers:
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ── Registry: all known providers ─────────────────────────────────────────
PROVIDER_REGISTRY = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "openai": OpenAIProvider,
    "grok": GrokProvider,
}

# Default priority: free/cheap first
DEFAULT_PRIORITY = ["ollama", "gemini", "groq", "openai", "grok"]

# Rate limits per provider (requests per minute) — used for smart throttling
PROVIDER_RATE_LIMITS = {
    "ollama": 999,  # Local — no rate limit
    "groq": 30,
    "gemini": 15,
    "openai": 60,
    "grok": 60,
}


class ProviderHealth:
    """Tracks health metrics for a single provider."""

    def __init__(self, name: str):
        self.name = name
        self.total_requests = 0
        self.failures = 0
        self.total_response_time = 0.0
        self.last_failure_time = 0.0
        self.last_request_time = 0.0
        self.consecutive_failures = 0
        self.rate_limited_until = 0.0  # Timestamp when rate limit cooldown expires

    @property
    def failure_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failures / self.total_requests

    @property
    def avg_response_time(self) -> float:
        successful = self.total_requests - self.failures
        if successful == 0:
            return 0.0
        return self.total_response_time / successful

    def record_success(self, response_time: float):
        self.total_requests += 1
        self.total_response_time += response_time
        self.consecutive_failures = 0
        self.last_request_time = time.time()

    def record_failure(self):
        self.total_requests += 1
        self.failures += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        self.last_request_time = time.time()

    def record_rate_limit(self, cooldown_seconds: float = 30.0):
        """Mark provider as rate-limited for a cooldown period."""
        self.rate_limited_until = time.time() + cooldown_seconds
        logger.info(f"⏳ {self.name} rate-limited — cooldown for {cooldown_seconds:.0f}s")

    def is_rate_limited(self) -> bool:
        """Check if provider is in rate limit cooldown."""
        return time.time() < self.rate_limited_until

    def is_healthy(self) -> bool:
        """Provider is unhealthy if 5+ consecutive failures in last 60s."""
        if self.consecutive_failures >= 5:
            if time.time() - self.last_failure_time < 60:
                return False
        return True

    def is_available(self) -> bool:
        """Provider is available if healthy AND not rate-limited."""
        return self.is_healthy() and not self.is_rate_limited()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "failures": self.failures,
            "failure_rate": round(self.failure_rate * 100, 1),
            "avg_response_time": round(self.avg_response_time, 2),
            "consecutive_failures": self.consecutive_failures,
            "healthy": self.is_healthy(),
            "rate_limited": self.is_rate_limited(),
        }


class ProviderManager:
    """
    Manages multiple LLM providers with round-robin rotation and intelligent fallback.

    Key scalability features:
    - Round-robin: distributes calls across all providers evenly (not just the first)
    - Dynamic throttle: adjusts delay based on each provider's rate limit
    - Rate limit cooldowns: temporarily skips providers that hit limits
    - Automatic recovery: rate-limited providers rejoin after cooldown
    """

    def __init__(self):
        # Read priority from env or use default
        priority_env = os.getenv("PROVIDER_PRIORITY", "")
        if priority_env.strip():
            self.priority = [p.strip().lower() for p in priority_env.split(",")]
        else:
            self.priority = DEFAULT_PRIORITY

        # Instantiate configured providers in priority order
        self.providers = []
        for name in self.priority:
            if name in PROVIDER_REGISTRY:
                provider = PROVIDER_REGISTRY[name]()
                if provider.is_configured():
                    self.providers.append(provider)
                    logger.info(f"✓ Provider registered: {name} (free={provider.is_free_tier})")
                else:
                    logger.info(f"⊘ Provider skipped (no API key): {name}")
            else:
                logger.warning(f"✗ Unknown provider in priority list: {name}")

        if not self.providers:
            logger.error("⚠ No providers configured! Set at least one API key in .env")

        # Health tracker per provider
        self.health: dict[str, ProviderHealth] = {
            p.name: ProviderHealth(p.name) for p in self.providers
        }

        # Retry config
        self.max_retries = int(os.getenv("PROVIDER_MAX_RETRIES", "2"))
        self.backoff_base = float(os.getenv("PROVIDER_BACKOFF_BASE", "1.0"))

        # Base throttle delay (overridden per-provider based on rate limits)
        self.base_min_delay = float(os.getenv("PROVIDER_MIN_DELAY", "3.0"))

        # Round-robin counter
        self._robin_index = 0

    def _get_provider_delay(self, provider_name: str) -> float:
        """Get the minimum delay for a provider based on its rate limit."""
        rpm = PROVIDER_RATE_LIMITS.get(provider_name, 30)
        # Add 20% safety margin
        return (60.0 / rpm) * 1.2

    def _throttle(self, provider_name: str):
        """Wait if necessary to respect rate limits for a provider."""
        health = self.health.get(provider_name)
        if health and health.last_request_time > 0:
            min_delay = self._get_provider_delay(provider_name)
            elapsed = time.time() - health.last_request_time
            if elapsed < min_delay:
                wait = min_delay - elapsed
                logger.info(f"⏳ Throttling {provider_name}: waiting {wait:.1f}s (rate limit protection)")
                time.sleep(wait)

    def _get_next_provider(self) -> list:
        """
        Get providers in round-robin order, starting with the next provider
        in rotation but falling back to others if it's unavailable.
        """
        n = len(self.providers)
        if n == 0:
            return []

        # Build ordered list starting from robin_index
        ordered = []
        for i in range(n):
            idx = (self._robin_index + i) % n
            provider = self.providers[idx]
            health = self.health[provider.name]
            if health.is_available():
                ordered.append(provider)

        # Advance robin index for next call
        self._robin_index = (self._robin_index + 1) % n

        # If no providers are available due to rate limits, include rate-limited ones
        # (they'll wait out the cooldown via throttle)
        if not ordered:
            logger.warning("⚠ All providers rate-limited! Trying anyway with delays...")
            for i in range(n):
                idx = (self._robin_index + i) % n
                provider = self.providers[idx]
                if self.health[provider.name].is_healthy():
                    ordered.append(provider)

        return ordered

    def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        Send a chat completion request through the provider chain.
        Uses round-robin rotation to distribute load across all providers.

        Returns:
            Response text from the first successful provider.

        Raises:
            RuntimeError if all providers fail.
        """
        errors = []
        providers_to_try = self._get_next_provider()

        for provider in providers_to_try:
            health = self.health[provider.name]

            # Wait if rate-limited (but don't skip — might be the only option)
            if health.is_rate_limited():
                wait = health.rate_limited_until - time.time()
                if wait > 0 and wait < 60:
                    logger.info(f"⏳ Waiting {wait:.1f}s for {provider.name} rate limit cooldown")
                    time.sleep(wait)

            # Try with retries
            for attempt in range(1, self.max_retries + 1):
                try:
                    # Throttle to prevent rate limit hits
                    self._throttle(provider.name)

                    start = time.time()
                    logger.info(
                        f"→ Calling {provider.name} (attempt {attempt}/{self.max_retries})"
                    )

                    result = provider.chat_completion(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )

                    elapsed = time.time() - start
                    health.record_success(elapsed)

                    logger.info(
                        f"✓ {provider.name} responded in {elapsed:.2f}s"
                    )

                    return result

                except Exception as e:
                    health.record_failure()
                    error_msg = f"{provider.name} attempt {attempt}: {type(e).__name__}: {str(e)[:200]}"
                    errors.append(error_msg)
                    logger.warning(f"✗ {error_msg}")

                    error_str = str(e).lower()

                    # Config/model error → skip to next provider
                    if "400" in str(type(e).__name__) or "bad request" in error_str or "decommissioned" in error_str or "not found" in error_str or "invalid" in error_str:
                        logger.warning(f"⏭ {provider.name}: config/model error — skipping to next provider")
                        break

                    # Rate limited → set cooldown and move to next provider immediately
                    if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str or "resource_exhausted" in error_str:
                        health.record_rate_limit(cooldown_seconds=45.0)
                        logger.warning(f"⏭ {provider.name}: rate limited — rotating to next provider")
                        break  # Don't retry, just move to next provider

                    # Other error → exponential backoff before retry
                    if attempt < self.max_retries:
                        wait = self.backoff_base * (2 ** (attempt - 1))
                        logger.info(f"⏳ Backoff {wait:.1f}s before retry")
                        time.sleep(wait)

            # All retries exhausted for this provider
            logger.warning(f"⏭ All retries exhausted for {provider.name}, trying next provider")

        # All providers failed
        error_summary = "\n".join(errors)
        raise RuntimeError(
            f"All providers failed.\n\nErrors:\n{error_summary}"
        )

    def get_health_report(self) -> list[dict]:
        """Return health metrics for all providers."""
        return [h.to_dict() for h in self.health.values()]

    def get_active_providers(self) -> list[str]:
        """Return names of all configured and healthy providers."""
        return [p.name for p in self.providers if self.health[p.name].is_healthy()]


# ── Singleton instance ────────────────────────────────────────────────────
_manager = None


def get_manager() -> ProviderManager:
    """Get the singleton ProviderManager instance."""
    global _manager
    if _manager is None:
        _manager = ProviderManager()
    return _manager
