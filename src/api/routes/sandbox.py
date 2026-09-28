"""Sandbox API - run small Python snippets under the AST guard.

Exposes :mod:`src.utils.code_sandbox` over HTTP so any client (the dashboard,
the ChatGPT app, an automation script) can use the same validated, resource
limited execution path.

Safety recap (see ``src/utils/code_sandbox.py`` for the details):

* imports restricted to an allow-list of pure modules,
* ``open``/``exec``/``eval``/``getattr``/dunder escapes rejected before running,
* executes with ``python -I`` in a throw-away directory, under CPU/RAM/fork
  rlimits and a wall-clock timeout,
* the child process gets a minimal environment, so API keys never leak.

It is a demo/utility guard, **not** a hard multi-tenant boundary - see the
docstring of the guard module.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from src.utils.logger import get_logger
from src.utils import code_sandbox

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/sandbox", tags=["sandbox"])


class PythonRunRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Python snippet to execute")
    timeout: Optional[int] = Field(
        code_sandbox.DEFAULT_TIMEOUT, ge=1, le=10, description="Wall-clock timeout in seconds"
    )


@router.get("/info")
async def sandbox_info():
    """Describe the guard: limits, allow-list and blocked features."""
    explain, limits = code_sandbox.describe()
    return {
        "guard": explain,
        "limits": limits,
        "allowed_modules": code_sandbox.allowed_modules(),
        "blocked": code_sandbox.blocked_features(),
    }


@router.post("/python")
async def run_python(request: PythonRunRequest):
    """Validate and execute a snippet; never raises for user errors."""
    result = code_sandbox.run_python(request.code, timeout=request.timeout or code_sandbox.DEFAULT_TIMEOUT)
    if result.get("stage") == "validation":
        # Not an API error: the guard rejected the code, and the reason matters.
        logger.info(f"Sandbox rejected snippet: {result.get('error')}")
    return result


@router.get("/health")
async def sandbox_health():
    try:
        code_sandbox.allowed_modules()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Sandbox unavailable: {exc}")
    return {"status": "ok", "guard": code_sandbox.describe()[0]}
