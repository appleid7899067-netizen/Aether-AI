"""Aether AI - FastAPI application entry point.

Router modules are imported lazily and individually: a module that needs a
desktop-only dependency (GUI automation, OCR, audio hardware, ...) is skipped
with a warning instead of taking the whole API down.  That lets the exact same
codebase run on a Windows desktop and inside a headless container (Render,
Docker, Kubernetes).
"""
import importlib
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DASHBOARD_FILE = Path(__file__).parent / "static" / "dashboard.html"
DASHBOARD_HTML = (
    _DASHBOARD_FILE.read_text(encoding="utf-8")
    if _DASHBOARD_FILE.exists()
    else "<h1>Aether AI</h1><p>Dashboard file missing.</p>"
)

# Every route module and the URL prefix it owns (used for the index page).
ROUTER_MODULES = {
    "chat": "/api/v1/chat",
    "tasks": "/api/v1/tasks",
    "settings": "/api/v1/settings",
    "openclaw": "/api/v1/openclaw",
    "security": "/api/v1/security",
    "bugbounty": "/api/v1/bugbounty",
    "bugbounty_auto": "/api/v1/bugbounty/auto",
    "voice": "/api/v1/voice",
    "memory": "/api/v1/memory",
    "voice_commands": "/api/v1/voice-commands",
    "plugins": "/api/v1/plugins",
    "developer": "/api/v1/developer",
    "discord": "/api/v1/discord",
    "workflows": "/api/v1/workflows",
    "monitor": "/api/v1/monitor",
    "proactive": "/api/v1/proactive",
    "control": "/api/v1/control",
    "intelligence": "/api/v1/intelligence",
    "evolution": "/api/v1/evolution",
    "autonomous": "/api/v1/autonomous",
    "live_testing": "/api/v1/live-testing",
    "v3": "/api/v1/v3",
    "n8n": "/api/v1/n8n",
    "desktop": "/api/v1/desktop",
}

# Modules that must never be loaded on a headless server (they need a display).
HEADLESS_BLOCKED = {"desktop", "control", "autonomous", "live_testing"}

# Populated at import time: module name -> prefix | error message
LOADED_ROUTERS: dict = {}
FAILED_ROUTERS: dict = {}


def _is_headless() -> bool:
    """True when there is no usable graphical session (Docker, Render, CI)."""
    import platform

    if platform.system() in ("Windows", "Darwin"):
        return False
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return True
    try:
        import pyautogui  # noqa: F401

        return False
    except Exception:  # noqa: BLE001
        return True


def load_routers(app: FastAPI) -> None:
    """Register every route module that can be imported in this environment."""
    headless = _is_headless()

    for name in ROUTER_MODULES:
        if headless and name in HEADLESS_BLOCKED:
            FAILED_ROUTERS[name] = "requires a graphical desktop session"
            continue
        try:
            module = importlib.import_module(f"src.api.routes.{name}")
            app.include_router(module.router)
            LOADED_ROUTERS[name] = ROUTER_MODULES[name]
        except Exception as exc:  # noqa: BLE001
            FAILED_ROUTERS[name] = f"{type(exc).__name__}: {exc}"
            logger.warning(f"Route module '{name}' disabled: {exc}")

    logger.info(
        f"Routers loaded: {len(LOADED_ROUTERS)}/{len(ROUTER_MODULES)}"
        + (f" | disabled: {list(FAILED_ROUTERS)}" if FAILED_ROUTERS else "")
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    # Live vision monitoring only makes sense with a screen attached.
    if _is_headless():
        logger.info("Headless environment detected - live vision monitoring skipped")
    else:
        try:
            from src.features.live_vision import start_live_monitoring

            start_live_monitoring()
            logger.info("[LIVE VISION] Real-time screen awareness active")
        except Exception as e:  # noqa: BLE001
            logger.info(f"Live vision disabled: {e}")

    if settings.enable_daily_reports:
        try:
            from src.intelligence.scheduler import start_intelligence_scheduler

            start_intelligence_scheduler()
            logger.info("Intelligence scheduler started")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Intelligence scheduler disabled: {e}")

    logger.info("Startup complete")
    yield

    logger.info("Shutting down Aether AI application")
    if not _is_headless():
        try:
            from src.features.live_vision import stop_live_monitoring

            stop_live_monitoring()
        except Exception:  # noqa: BLE001
            pass

    try:
        from src.intelligence.scheduler import stop_intelligence_scheduler

        stop_intelligence_scheduler()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(
    title="Aether AI API",
    description=(
        "Next-generation autonomous AI assistant API - chat, memory, voice, "
        "bug-bounty recon, monitoring and desktop control."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS - "*" by default so the dashboard / Electron UI can talk to the API from
# any host (Render serves the API from a different origin than the static site).
_origins = settings.get_allowed_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins and _origins != ["*"] else ["*"],
    allow_credentials=False if "*" in _origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.time() - start_time:.4f}"
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """Browser dashboard (chat + status). API metadata lives at /api."""
    return HTMLResponse(DASHBOARD_HTML)


@app.get("/api")
async def api_index():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
        "routers": LOADED_ROUTERS,
        "disabled_routers": FAILED_ROUTERS,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "components": {
            "api": "online",
            "routers_loaded": len(LOADED_ROUTERS),
            "routers_disabled": len(FAILED_ROUTERS),
            "providers_configured": settings.ai_provider or "auto",
        },
    }


@app.post("/chat")
async def chat_endpoint(payload: dict):
    """Legacy/simple chat endpoint (kept for scripts and webhooks).

    For the full-featured API use ``POST /api/v1/chat/conversation``.
    """
    from src.cognitive.llm.inference import ConversationRequest, conversation_engine

    message = payload.get("message") or payload.get("prompt") or ""
    if not message:
        return JSONResponse(
            status_code=422, content={"detail": "Field 'message' or 'prompt' is required"}
        )

    request = ConversationRequest(
        user_input=message,
        session_id=payload.get("session_id", "default"),
        stream=False,
    )
    try:
        response = await conversation_engine.process_conversation(request)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Chat request failed: {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Chat is unavailable: no AI provider answered. Add an API key "
                    "(GROQ_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY ...) in the "
                    "environment and restart the service."
                ),
                "error": str(exc),
            },
        )
    return {
        "content": response.content,
        "session_id": response.session_id,
        "intent": response.intent.value if response.intent else None,
        "provider": response.ai_response.provider,
        "model": response.ai_response.model,
        "tokens_used": response.ai_response.tokens_used,
        "cost_usd": response.ai_response.cost_usd,
        "latency_ms": response.ai_response.latency_ms,
    }


load_routers(app)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", settings.api_port))
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.environment == "development",
    )
