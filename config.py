"""
Blogy — Configuration Management
Centralized config for API keys, model settings, and pipeline parameters.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Provider API Keys ──────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROK_API_KEY: str = os.getenv("GROK_API_KEY", "")

    # ── Provider Priority ──────────────────────────────────────────────
    PROVIDER_PRIORITY: str = os.getenv("PROVIDER_PRIORITY", "gemini,groq,openai,grok")

    # ── Temperature settings per pipeline stage (precision → creativity)
    TEMPERATURES = {
        "keyword_intelligence": 0.3,
        "serp_analysis": 0.4,
        "content_strategy": 0.5,
        "blog_generation": 0.7,
        "internal_linking": 0.3,
    }

    # ── Internal site pages for linking simulation ─────────────────────
    INTERNAL_PAGES = [
        {"url": "/pricing", "title": "Pricing Plans", "description": "Explore our flexible pricing tiers designed for teams of every size."},
        {"url": "/features", "title": "Platform Features", "description": "Discover the full suite of tools and capabilities our platform offers."},
        {"url": "/case-studies", "title": "Case Studies", "description": "Real-world success stories from companies using our platform."},
        {"url": "/blog", "title": "Blog", "description": "Insights, guides, and thought leadership articles."},
        {"url": "/docs", "title": "Documentation", "description": "Technical documentation and API reference guides."},
    ]

    # ── SEO target thresholds ──────────────────────────────────────────
    KEYWORD_DENSITY_MIN = 0.5
    KEYWORD_DENSITY_MAX = 2.5
    KEYWORD_DENSITY_TARGET_MIN = 1.0
    KEYWORD_DENSITY_TARGET_MAX = 2.0
    FLESCH_TARGET = 60


settings = Settings()
