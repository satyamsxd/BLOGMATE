"""
Blogy — Pipeline Orchestrator
Sequences all 6 pipeline stages, accumulates structured context,
and supports both synchronous and generator-based streaming execution.
"""

import time
from pipeline import keyword_intelligence, serp_analyzer, content_strategy
from pipeline import blog_generator, seo_analyzer, internal_linker


STAGE_CONFIG = [
    {"name": "Keyword Intelligence", "number": 1},
    {"name": "SERP Analysis", "number": 2},
    {"name": "Content Strategy", "number": 3},
    {"name": "Blog Generation", "number": 4},
    {"name": "SEO Validation", "number": 5},
    {"name": "Internal Linking", "number": 6},
]

TOTAL_STAGES = len(STAGE_CONFIG)


def run(keyword: str, on_stage_complete=None) -> dict:
    """
    Execute the full content intelligence pipeline (synchronous).

    Args:
        keyword: Primary keyword to process.
        on_stage_complete: Optional callback(stage_name, stage_number, total_stages, result)

    Returns:
        Unified PipelineResult dict with all stage outputs.
    """
    result = {}
    for stage_event in run_streaming(keyword):
        if stage_event.get("type") == "stage_complete":
            if on_stage_complete:
                on_stage_complete(
                    stage_event["stage"],
                    stage_event["stage_number"],
                    stage_event["total_stages"],
                    stage_event.get("data", {}),
                )
        elif stage_event.get("type") == "done":
            result = stage_event["result"]
    return result


def run_streaming(keyword: str):
    """
    Generator-based pipeline execution that yields stage events.

    Yields dicts with:
        {"type": "stage_start", "stage": "...", "stage_number": N, "total_stages": 6}
        {"type": "stage_complete", "stage": "...", "stage_number": N, "total_stages": 6, "duration": float, "data": {...}}
        {"type": "done", "result": {...}}
    """
    timings = {}

    # ── Stage 1: Keyword Intelligence ──
    yield {"type": "stage_start", "stage": "Keyword Intelligence", "stage_number": 1, "total_stages": TOTAL_STAGES}
    t0 = time.time()
    ki_result = keyword_intelligence.run(keyword)
    timings["keyword_intelligence"] = round(time.time() - t0, 2)
    yield {"type": "stage_complete", "stage": "Keyword Intelligence", "stage_number": 1, "total_stages": TOTAL_STAGES, "duration": timings["keyword_intelligence"], "data": ki_result}

    # ── Stage 2: SERP Reverse Engineering ──
    yield {"type": "stage_start", "stage": "SERP Analysis", "stage_number": 2, "total_stages": TOTAL_STAGES}
    t0 = time.time()
    serp_result = serp_analyzer.run(ki_result)
    timings["serp_analysis"] = round(time.time() - t0, 2)
    yield {"type": "stage_complete", "stage": "SERP Analysis", "stage_number": 2, "total_stages": TOTAL_STAGES, "duration": timings["serp_analysis"], "data": serp_result}

    # ── Stage 3: Content Strategy ──
    yield {"type": "stage_start", "stage": "Content Strategy", "stage_number": 3, "total_stages": TOTAL_STAGES}
    t0 = time.time()
    cs_result = content_strategy.run(ki_result, serp_result)
    timings["content_strategy"] = round(time.time() - t0, 2)
    yield {"type": "stage_complete", "stage": "Content Strategy", "stage_number": 3, "total_stages": TOTAL_STAGES, "duration": timings["content_strategy"], "data": cs_result}

    # ── Stage 4: Blog Generation ──
    yield {"type": "stage_start", "stage": "Blog Generation", "stage_number": 4, "total_stages": TOTAL_STAGES}
    t0 = time.time()
    blog_result = blog_generator.run(ki_result, cs_result)
    timings["blog_generation"] = round(time.time() - t0, 2)
    yield {"type": "stage_complete", "stage": "Blog Generation", "stage_number": 4, "total_stages": TOTAL_STAGES, "duration": timings["blog_generation"], "data": blog_result}

    # ── Stage 5: SEO + Quality Validation ──
    yield {"type": "stage_start", "stage": "SEO Validation", "stage_number": 5, "total_stages": TOTAL_STAGES}
    t0 = time.time()
    seo_result = seo_analyzer.run(blog_result, ki_result, cs_result)
    timings["seo_validation"] = round(time.time() - t0, 2)
    yield {"type": "stage_complete", "stage": "SEO Validation", "stage_number": 5, "total_stages": TOTAL_STAGES, "duration": timings["seo_validation"], "data": seo_result}

    # ── Stage 6: Internal Linking ──
    yield {"type": "stage_start", "stage": "Internal Linking", "stage_number": 6, "total_stages": TOTAL_STAGES}
    t0 = time.time()
    links_result = internal_linker.run(blog_result)
    timings["internal_linking"] = round(time.time() - t0, 2)
    yield {"type": "stage_complete", "stage": "Internal Linking", "stage_number": 6, "total_stages": TOTAL_STAGES, "duration": timings["internal_linking"], "data": links_result}

    # ── Assemble Strategy Justification ──
    seo_score = seo_result.get("seo_score", {}).get("total_score", 0)
    snippet_score = seo_result.get("snippet_readiness", {}).get("score", 0)
    naturalness_score = seo_result.get("naturalness", {}).get("score", 0)
    gaps_addressed = len(serp_result.get("content_gaps", []))

    strategy_justification = {
        "why_this_can_rank": [
            f"Targets {len(ki_result.get('ranking_feasibility', []))} feasible keywords with low-to-medium competition",
            f"Addresses {gaps_addressed} identified content gaps that competitors miss",
            f"SEO score of {seo_score}/100 indicates strong on-page optimization",
            f"Content structured with {seo_result.get('snippet_readiness', {}).get('elements_present', 0)} snippet-ready elements for featured snippet capture",
            f"GEO-optimized with extractable definitions, lists, and structured data for AI answer engines",
        ],
        "competitive_advantages": [
            f"Naturalness score {naturalness_score}/100 — avoids robotic AI patterns",
            f"Snippet readiness {snippet_score}% — structured for zero-click SERP features",
            f"Section-by-section generation preserves narrative flow and reader engagement",
            f"Intent-aligned content ({ki_result.get('intent_classification', 'unknown')}) matches real user search behavior",
        ],
    }

    total_time = round(sum(timings.values()), 2)

    final_result = {
        "keyword": keyword,
        "keyword_intelligence": ki_result,
        "serp_analysis": serp_result,
        "content_strategy": cs_result,
        "blog_content": blog_result,
        "seo_analysis": seo_result,
        "internal_links": links_result,
        "strategy_justification": strategy_justification,
        "pipeline_timing": {**timings, "total": total_time},
    }

    yield {"type": "done", "result": final_result}
