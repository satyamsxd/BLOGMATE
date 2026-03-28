"""
Blogy — Stage 6: Internal Linking Intelligence
Identifies natural anchor text opportunities to link to internal pages.
Uses the ProviderManager for automatic multi-provider fallback.
"""

import json
from config import settings
from pipeline.prompt_flow import PROMPTS
from pipeline.json_parser import parse_llm_json
from providers.manager import get_manager


def run(blog_content: dict) -> dict:
    """
    Analyze blog content and suggest contextually relevant internal links.

    Args:
        blog_content: Output from blog_generator.run()

    Returns:
        Dict with suggestions list.
    """
    manager = get_manager()
    prompt_cfg = PROMPTS["internal_linking"]

    internal_pages_str = json.dumps(settings.INTERNAL_PAGES, indent=2)
    blog_text = blog_content.get("full_markdown", "")

    messages = [
        {"role": "system", "content": prompt_cfg["system"]},
        {
            "role": "user",
            "content": prompt_cfg["user"].format(
                blog_content=blog_text[:3000],
                internal_pages=internal_pages_str,
            ),
        },
    ]

    raw = manager.complete(
        messages=messages,
        temperature=settings.TEMPERATURES["internal_linking"],
    )

    result = parse_llm_json(raw)

    if "suggestions" not in result:
        result = {"suggestions": []}

    return result
