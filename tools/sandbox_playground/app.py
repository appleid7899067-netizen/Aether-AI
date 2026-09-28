"""Sandbox playground - a small web app to try Aether AI's sandbox features.

Three demos, all backed by real code from the repository:

* ``POST /api/python`` - validated Python snippet (AST allow-list + isolated
  subprocess with rlimits) via ``sandbox_guard.run_python``.
* ``POST /api/shell``  - the repository's own ``SafeScriptExecutor`` with its
  allow/deny command lists.
* ``POST /api/plugin`` - the repository's ``PluginSandbox`` running a plugin
  class in a separate process with a timeout.

Run:
    uvicorn tools.sandbox_playground.app:app --host 0.0.0.0 --port 8100

This is a demo harness for local/experimental use - do not expose it to the
public internet without adding authentication in front of it.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.sandbox_playground import sandbox_guard  # noqa: E402

app = FastAPI(
    title="Aether Sandbox Playground",
    description="Try Aether AI's sandbox layers from the browser.",
    version="1.0.0",
)

PAGE = (Path(__file__).parent / "playground.html").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class PythonRequest(BaseModel):
    code: str = Field(..., description="Python snippet to run")
    timeout: Optional[int] = Field(None, ge=1, le=10)


class ShellRequest(BaseModel):
    command: str = Field(..., min_length=1, description="Command name, e.g. echo")
    args: List[str] = Field(default_factory=list)


class PluginRequest(BaseModel):
    plugin: str = Field("fibonacci", description="Plugin name under demo_plugins/")
    params: dict = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(PAGE)


@app.get("/api/info")
async def info():
    explain, limits = sandbox_guard.describe()
    return {
        "guard": explain,
        "limits": limits,
        "allowed_modules": sandbox_guard.allowed_modules(),
        "blocked": sandbox_guard.blocked_features(),
        "samples": SAMPLES,
    }


# --------------------------------------------------------------------------- #
# 1. Python sandbox
# --------------------------------------------------------------------------- #
@app.post("/api/python")
async def run_python(request: PythonRequest):
    result = sandbox_guard.run_python(request.code, timeout=request.timeout or 5)
    return result


# --------------------------------------------------------------------------- #
# 2. Safe command execution (uses the repository's own executor)
# --------------------------------------------------------------------------- #
def _safe_executor():
    from src.action.automation.script_executor import SafeScriptExecutor

    return SafeScriptExecutor(timeout=5)


@app.get("/api/shell/commands")
async def shell_commands():
    executor = _safe_executor()
    return {
        "allowed": sorted(executor.SAFE_COMMANDS),
        "blocked": sorted(executor.DANGEROUS_COMMANDS),
    }


@app.post("/api/shell")
async def run_shell(request: ShellRequest):
    executor = _safe_executor()
    result = executor.execute_command(request.command, args=request.args)
    return {
        "ok": result.success,
        "command": " ".join([request.command, *request.args]),
        "stdout": result.output,
        "error": result.error,
        "exit_code": result.exit_code,
        "execution_time": round(result.execution_time, 3),
    }


# --------------------------------------------------------------------------- #
# 3. Plugin sandbox (separate process + timeout)
# --------------------------------------------------------------------------- #
@app.get("/api/plugin/list")
async def plugin_list():
    plugins = sorted(
        p.stem for p in (Path(__file__).parent / "demo_plugins").glob("*_plugin.py")
    )
    return {"plugins": [p.replace("_plugin", "") for p in plugins]}


@app.post("/api/plugin")
async def run_plugin(request: PluginRequest):
    from src.core.plugins.sandbox import PluginSandbox

    name = request.plugin.strip().replace("-", "_")
    if not name.isidentifier():
        raise HTTPException(status_code=400, detail="Invalid plugin name")

    module = f"tools.sandbox_playground.demo_plugins.{name}_plugin"
    class_name = "".join(part.capitalize() for part in name.split("_")) + "Plugin"

    sandbox = PluginSandbox(timeout_seconds=10)
    result = await sandbox.execute_isolated(module, class_name, request.params)
    return result


# --------------------------------------------------------------------------- #
# Samples shown in the UI
# --------------------------------------------------------------------------- #
SAMPLES = {
    "fibonacci": "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\n\nprint([fib(i) for i in range(12)])",
    "thai_text": "text = 'สวัสดีครับ Aether'\nprint(text.upper())\nprint('จำนวนตัวอักษร:', len(text))",
    "stats": "import random, statistics\nrandom.seed(7)\ndata = [random.randint(1, 100) for _ in range(20)]\nprint('mean:', round(statistics.mean(data), 2), 'median:', statistics.median(data))",
    "blocked_import": "import os\nprint(os.listdir('/'))",
    "blocked_escape": "print(().__class__.__bases__[0].__subclasses__()[:5])",
    "timeout_demo": "while True:\n    pass",
}
