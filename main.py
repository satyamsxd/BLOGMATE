"""
Blogy — FastAPI Application
Main entry point for the AI Content Intelligence Engine.
Supports real-time SSE streaming, provider health monitoring, and generation history.
"""

import json
import traceback
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pipeline import orchestrator
from providers.manager import get_manager

app = FastAPI(title="Blogy — AI Content Intelligence Engine")

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    keyword: str


# ── In-memory generation history ──────────────────────────────────────────
generation_history: list[dict] = []


@app.post("/api/generate")
def generate_blog(req: GenerateRequest):
    """Full pipeline execution — returns complete result."""
    try:
        keyword = req.keyword.strip()
        if not keyword:
            return JSONResponse(status_code=400, content={"error": "Keyword is required"})

        result = orchestrator.run(keyword)

        # Store in history
        generation_history.append({
            "keyword": keyword,
            "seo_score": result.get("seo_analysis", {}).get("seo_score", {}).get("total_score", 0),
            "word_count": result.get("blog_content", {}).get("total_word_count", 0),
            "timing": result.get("pipeline_timing", {}).get("total", 0),
        })

        return JSONResponse(content=result)

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/generate/stream")
async def generate_blog_stream(req: GenerateRequest):
    """Streaming pipeline execution — sends real-time stage progress via SSE."""
    keyword = req.keyword.strip()
    if not keyword:
        return JSONResponse(status_code=400, content={"error": "Keyword is required"})

    def event_stream():
        try:
            for event in orchestrator.run_streaming(keyword):
                event_type = event.get("type", "unknown")

                if event_type == "stage_start":
                    sse_data = {
                        "type": "stage_start",
                        "stage": event["stage"],
                        "stage_number": event["stage_number"],
                        "total_stages": event["total_stages"],
                    }
                    yield f"data: {json.dumps(sse_data)}\n\n"

                elif event_type == "stage_complete":
                    sse_data = {
                        "type": "stage_complete",
                        "stage": event["stage"],
                        "stage_number": event["stage_number"],
                        "total_stages": event["total_stages"],
                        "duration": event.get("duration", 0),
                    }
                    yield f"data: {json.dumps(sse_data)}\n\n"

                elif event_type == "done":
                    result = event["result"]

                    # Store in history
                    generation_history.append({
                        "keyword": keyword,
                        "seo_score": result.get("seo_analysis", {}).get("seo_score", {}).get("total_score", 0),
                        "word_count": result.get("blog_content", {}).get("total_word_count", 0),
                        "timing": result.get("pipeline_timing", {}).get("total", 0),
                    })

                    sse_data = {
                        "type": "done",
                        "result": result,
                    }
                    yield f"data: {json.dumps(sse_data)}\n\n"

        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Provider Health Endpoints ─────────────────────────────────────────────

@app.get("/api/providers/health")
async def provider_health():
    """Return health metrics for all configured providers."""
    try:
        manager = get_manager()
        return JSONResponse(content={
            "providers": manager.get_health_report(),
            "active": manager.get_active_providers(),
            "priority": [p.name for p in manager.providers],
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/providers/active")
async def active_providers():
    """Return list of active (configured + healthy) providers."""
    try:
        manager = get_manager()
        return JSONResponse(content={
            "active": manager.get_active_providers(),
            "total_configured": len(manager.providers),
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/history")
async def get_history():
    """Return generation history."""
    return JSONResponse(content={"history": list(reversed(generation_history))})


# ── Serve frontend static files (must be last) ──────────────────────────
app.mount("/", StaticFiles(directory="static", html=True), name="static")
