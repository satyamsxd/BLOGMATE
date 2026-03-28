"""
Blogy — Stage 2: SERP Reverse Engineering Layer
Simulates SERP analysis to infer heading structures, content depth patterns,
keyword positioning, and content gaps.
Uses the ProviderManager for automatic multi-provider fallback.
"""

import json
from config import settings
from pipeline.prompt_flow import PROMPTS
from pipeline.json_parser import parse_llm_json
from providers.manager import get_manager


def run(keyword_intel: dict) -> dict:
    """
    Reverse-engineer typical SERP structure for the given keyword cluster.

    Args:
        keyword_intel: Output from keyword_intelligence.run()

    Returns:
        Dict with typical_heading_structure, content_depth_patterns,
        keyword_positioning, content_gaps, gap_report_summary.
    """
    manager = get_manager()
    prompt_cfg = PROMPTS["serp_analysis"]

    # Pick top 5 feasible keywords for the prompt
    feasibility = keyword_intel.get("ranking_feasibility", [])
    top_keywords = sorted(feasibility, key=lambda x: x.get("score", 0), reverse=True)[:5]
    top_keywords_str = json.dumps(top_keywords, indent=2)

    messages = [
        {"role": "system", "content": prompt_cfg["system"]},
        {
            "role": "user",
            "content": prompt_cfg["user"].format(
                primary_keyword=keyword_intel["primary_keyword"],
                semantic_clusters=json.dumps(keyword_intel.get("semantic_clusters", {})),
                intent_classification=keyword_intel.get("intent_classification", "informational"),
                top_keywords=top_keywords_str,
            ),
        },
    ]

    raw = manager.complete(
        messages=messages,
        temperature=settings.TEMPERATURES["serp_analysis"],
    )

    result = parse_llm_json(raw)

    # Defaults
    defaults = {
        "typical_heading_structure": [],
        "content_depth_patterns": {},
        "keyword_positioning": {},
        "content_gaps": [],
        "gap_report_summary": "",
    }
    for key, default in defaults.items():
        result.setdefault(key, default)

    return result
