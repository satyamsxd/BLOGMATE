"""
Blogy — Stage 3: Content Strategy Engine
Generates the full content blueprint including SEO title, outline,
keyword mapping, tone strategy, and GEO optimization layer.
Uses the ProviderManager for automatic multi-provider fallback.
"""

import json
from config import settings
from pipeline.prompt_flow import PROMPTS
from pipeline.json_parser import parse_llm_json
from providers.manager import get_manager


def run(keyword_intel: dict, serp_analysis: dict) -> dict:
    """
    Build a comprehensive content strategy blueprint.

    Args:
        keyword_intel: Output from keyword_intelligence.run()
        serp_analysis: Output from serp_analyzer.run()

    Returns:
        Dict with seo_title, meta_description, outline, section_keyword_map,
        tone_strategy, geo_optimization.
    """
    manager = get_manager()
    prompt_cfg = PROMPTS["content_strategy"]

    # Prepare inputs
    feasibility = keyword_intel.get("ranking_feasibility", [])
    top_keywords = sorted(feasibility, key=lambda x: x.get("score", 0), reverse=True)[:8]

    messages = [
        {"role": "system", "content": prompt_cfg["system"]},
        {
            "role": "user",
            "content": prompt_cfg["user"].format(
                primary_keyword=keyword_intel["primary_keyword"],
                intent_classification=keyword_intel.get("intent_classification", "informational"),
                content_gaps=json.dumps(serp_analysis.get("content_gaps", []), indent=2),
                top_keywords=json.dumps(top_keywords, indent=2),
                lsi_keywords=json.dumps(keyword_intel.get("lsi_keywords", [])),
                question_queries=json.dumps(keyword_intel.get("question_queries", [])),
            ),
        },
    ]

    raw = manager.complete(
        messages=messages,
        temperature=settings.TEMPERATURES["content_strategy"],
    )

    result = parse_llm_json(raw)

    # Defaults
    defaults = {
        "seo_title": "",
        "meta_description": "",
        "outline": [],
        "section_keyword_map": {},
        "tone_strategy": {},
        "geo_optimization": {},
    }
    for key, default in defaults.items():
        result.setdefault(key, default)

    return result
