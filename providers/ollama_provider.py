"""
Blogy — Ollama Provider (LOCAL)
Connects to locally-running Ollama server for UNLIMITED, FREE generation.
No API keys needed. No rate limits. No quotas.

Setup:
  1. Install Ollama: https://ollama.com/download
  2. Pull a model: ollama pull llama3.1:8b  (or mistral, qwen2.5:7b, etc.)
  3. Ollama runs automatically at http://localhost:11434
"""

import os
import httpx
from providers.base import BaseProvider


class OllamaProvider(BaseProvider):
    name = "ollama"
    is_free_tier = True  # Completely free — runs locally

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self._available = None  # Cache availability check

    def is_configured(self) -> bool:
        """Check if Ollama is running and has at least one model."""
        if self._available is not None:
            return self._available

        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                if models:
                    # Check if the configured model is available
                    model_names = [m.get("name", "") for m in models]
                    # Ollama model names can have tags like "llama3.1:8b"
                    # Also match without tag: "llama3.1" matches "llama3.1:latest"
                    configured = self.model.lower()
                    found = any(
                        configured in name.lower() or name.lower().startswith(configured.split(":")[0])
                        for name in model_names
                    )
                    if not found and models:
                        # Use the first available model as fallback
                        self.model = models[0].get("name", self.model)
                    self._available = True
                    return True
            self._available = False
            return False
        except Exception:
            self._available = False
            return False

    def chat_completion(self, messages, temperature=0.7, max_tokens=4096) -> str:
        """Send chat completion to local Ollama server."""
        # Use Ollama's OpenAI-compatible chat endpoint
        response = httpx.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
            timeout=120.0,  # Local models can be slower, generous timeout
        )

        if response.status_code != 200:
            raise Exception(f"Ollama error {response.status_code}: {response.text[:300]}")

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            raise Exception("Ollama returned empty response")

        return content
