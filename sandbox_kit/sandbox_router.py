"""Optional FastAPI router - drop-in for projects that already use FastAPI.

    from fastapi import FastAPI
    from sandbox_router import router as sandbox_router   # this file, renamed if you like

    app = FastAPI()
    app.include_router(sandbox_router)

Gives you:
    GET  /api/v1/sandbox/info
    GET  /api/v1/sandbox/health
    POST /api/v1/sandbox/python   {"code": "...", "timeout": 5}

No auth here on purpose - put your normal API auth in front of it.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

import code_sandbox

router = APIRouter(prefix="/api/v1/sandbox", tags=["sandbox"])


class PythonRunRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Python snippet to execute")
    timeout: Optional[int] = Field(
        code_sandbox.DEFAULT_TIMEOUT, ge=1, le=10, description="Wall-clock timeout in seconds"
    )


@router.get("/info")
async def sandbox_info():
    description, limits = code_sandbox.describe()
    return {
        "guard": description,
        "limits": limits,
        "allowed_modules": code_sandbox.allowed_modules(),
        "blocked": code_sandbox.blocked_features(),
    }


@router.get("/health")
async def sandbox_health():
    try:
        code_sandbox.allowed_modules()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Sandbox unavailable: {exc}")
    return {"status": "ok"}


@router.post("/python")
async def run_python(request: PythonRunRequest):
    """Validation failures are returned as 200 with ok=false - they are user input
    problems, not server errors."""
    return code_sandbox.run_python(
        request.code, timeout=request.timeout or code_sandbox.DEFAULT_TIMEOUT
    )
