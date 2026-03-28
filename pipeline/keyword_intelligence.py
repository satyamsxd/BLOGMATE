"""
Blogy — Stage 1: Keyword Intelligence Layer
Converts a primary keyword into semantic clusters, intent classification,
and ranking feasibility scores.
Uses the ProviderManager for automatic multi-provider fallback.
"""

import json
from config import settings
from pipeline.prompt_flow import PROMPTS
from pipeline.json_parser import parse_llm_json
from providers.manager import get_manager


def run(keyword: str) -> dict:
    """
    Analyze a keyword and return structured intelligence.

    Args:
        keyword: The primary keyword to analyze.

    Returns:
        Dict with semantic_clusters, long_tail_variations, lsi_keywords,
        question_queries, intent_classification, intent_reasoning,
        and ranking_feasibility.
    """
    manager = get_manager()
    prompt_cfg = PROMPTS["keyword_intelligence"]

    messages = [
        {"role": "system", "content": prompt_cfg["system"]},
        {"role": "user", "content": prompt_cfg["user"].format(keyword=keyword)},
    ]

    raw = manager.complete(
        messages=messages,
        temperature=settings.TEMPERATURES["keyword_intelligence"],
    )

    result = parse_llm_json(raw)

    # Ensure required keys exist with defaults
    defaults = {
        "primary_keyword": keyword,
        "semantic_clusters": {},
        "long_tail_variations": [],
        "lsi_keywords": [],
        "question_queries": [],
        "intent_classification": "informational",
        "intent_reasoning": "",
        "ranking_feasibility": [],
    }
    for key, default in defaults.items():
        result.setdefault(key, default)

    return result
