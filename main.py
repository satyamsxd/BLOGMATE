"""
Blogmate — FastAPI Application
Main entry point for the AI Content Intelligence Engine.
Supports real-time SSE streaming, provider health monitoring, and generation history.
"""

import json
import os
import traceback
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pipeline import orchestrator
from providers.manager import get_manager

# ── Rate Limiter setup ────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Blogmate — AI Content Intelligence Engine")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS: restrict to configured allowed origins ──────────────────────────
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── API Key Authentication ────────────────────────────────────────────────
API_KEY = os.getenv("BLOGMATE_API_KEY", "")

def verify_api_key(request: Request):
    """Dependency: validates X-API-Key header on protected routes."""
    if not API_KEY:
        # No key configured → auth disabled (dev mode)
        return
    client_key = request.headers.get("X-API-Key", "")
    if client_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include 'X-API-Key: <your-key>' header.",
        )


class GenerateRequest(BaseModel):
    keyword: str


# ── In-memory generation history ──────────────────────────────────────────
generation_history: list[dict] = []


@app.post("/api/generate")
@limiter.limit("10/minute")
def generate_blog(request: Request, req: GenerateRequest, _: None = Depends(verify_api_key)):
    """Full pipeline execution — returns complete result. Rate limited: 10/min per IP."""
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
@limiter.limit("10/minute")
async def generate_blog_stream(request: Request, req: GenerateRequest, _: None = Depends(verify_api_key)):
    """Streaming pipeline execution — sends real-time stage progress via SSE. Rate limited: 10/min per IP."""
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
@limiter.limit("60/minute")
async def provider_health(request: Request, _: None = Depends(verify_api_key)):
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
@limiter.limit("60/minute")
async def active_providers(request: Request, _: None = Depends(verify_api_key)):
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
@limiter.limit("60/minute")
async def get_history(request: Request, _: None = Depends(verify_api_key)):
    """Return generation history."""
    return JSONResponse(content={"history": list(reversed(generation_history))})


# ── Serve frontend static files (must be last) ──────────────────────────
app.mount("/", StaticFiles(directory="static", html=True), name="static")
