"""Quick end-to-end pipeline test."""
import httpx, json, sys

print("Starting generation test...")
sys.stdout.flush()

try:
    with httpx.stream(
        "POST",
        "http://localhost:8000/api/generate/stream",
        json={"keyword": "email marketing tips"},
        timeout=httpx.Timeout(300.0),
    ) as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                event = json.loads(line[6:])
                t = event["type"]
                if t == "stage_start":
                    print(f"  >> Stage {event['stage_number']}: {event['stage']} starting...")
                elif t == "stage_complete":
                    print(f"  OK Stage {event['stage_number']}: {event['stage']} done ({event['duration']}s)")
                elif t == "done":
                    result = event["result"]
                    seo = result.get("seo_analysis", {}).get("seo_score", {})
                    blog = result.get("blog_content", {})
                    timing = result.get("pipeline_timing", {})
                    print(f"\n=== GENERATION COMPLETE ===")
                    print(f"SEO Score: {seo.get('total_score', 0)}/100")
                    print(f"Word Count: {blog.get('total_word_count', 0)}")
                    print(f"Sections: {len(blog.get('sections', []))}")
                    print(f"Total Time: {timing.get('total', 0)}s")
                    title = result.get("content_strategy", {}).get("seo_title", "N/A")
                    print(f"Title: {title}")
                elif t == "error":
                    print(f"  ERROR: {event['error']}")
                sys.stdout.flush()
except Exception as e:
    print(f"EXCEPTION: {e}")
