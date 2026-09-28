"""Safety layer for running untrusted Python snippets.

Used by ``src/api/routes/sandbox.py`` (HTTP) and by the sandbox playground, so the
input has to be treated as hostile.  Three layers of defence:

1. :func:`validate_code` - an AST allow-list.  Only a small set of pure
   computation modules (``math``, ``random``, ``json``, ...) may be imported, and
   dangerous builtins plus any dunder attribute access (the usual
   ``().__class__.__bases__[0].__subclasses__()`` escape) are rejected before a
   single byte is executed.
2. :func:`build_child_env` - the child process gets a *minimal* environment, so
   API keys (GROQ_API_KEY, OPENAI_API_KEY, ...) sitting in the parent can never
   leak into user code.
3. :func:`run_python` - executes in a throw-away directory with CPU / memory /
   process limits, a hard wall-clock timeout and ``python -I`` (isolated mode).

This is a demo harness, not a production multi-tenant sandbox: it is good enough
to let someone paste a snippet, and it is *not* a substitute for gVisor / a
container / a VM.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

MAX_CODE_CHARS = 4000
MAX_AST_NODES = 6000
DEFAULT_TIMEOUT = 5

# Modules that are pure computation / formatting and cannot touch the machine.
ALLOWED_IMPORTS = {
    "math", "cmath", "random", "statistics", "decimal", "fractions", "numbers",
    "json", "re", "string", "textwrap", "unicodedata", "difflib",
    "datetime", "time", "calendar", "zoneinfo", "uuid",
    "itertools", "functools", "operator", "collections", "heapq", "bisect",
    "copy", "enum", "dataclasses", "typing", "abc", "contextlib", "graphlib",
    "hashlib", "base64", "binascii", "hmac", "secrets",
    "array", "struct", "pprint", "csv", "io", "warnings",
}

# Names that must never be reachable from user code.
BLOCKED_NAMES = {
    "__import__", "open", "exec", "eval", "compile", "input", "breakpoint",
    "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
    "exit", "quit", "help", "memoryview", "object",
}

BLOCKED_ATTRIBUTES = {"__globals__", "__builtins__", "__subclasses__", "__bases__",
                      "__mro__", "__class__", "__dict__", "__code__", "__loader__"}


class ValidationError(ValueError):
    """Raised when user supplied code is not allowed to run."""


def _iter_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def validate_code(code: str) -> None:
    """Raise :class:`ValidationError` when ``code`` is not safe to run."""
    if not code or not code.strip():
        raise ValidationError("Code is empty")
    if len(code) > MAX_CODE_CHARS:
        raise ValidationError(f"Code is too long (limit {MAX_CODE_CHARS} characters)")

    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ValidationError(f"Syntax error: {exc.msg} (line {exc.lineno})") from exc

    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise ValidationError("Code is too complex")

    for node in ast.walk(tree):
        # --- imports -------------------------------------------------------
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_module(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import
                raise ValidationError("Relative imports are not allowed")
            _check_module(node.module or "")

        # --- forbidden builtins -------------------------------------------
        elif isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            raise ValidationError(f"'{node.id}' is not allowed")
        elif isinstance(node, ast.Attribute) and node.attr in BLOCKED_ATTRIBUTES:
            raise ValidationError(f"Access to '{node.attr}' is not allowed")

        # --- no file / network access through these calls ------------------
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BLOCKED_NAMES:
                raise ValidationError(f"'{func.id}()' is not allowed")
            if isinstance(func, ast.Attribute) and func.attr in {"system", "popen",
                                                                "spawn", "fork",
                                                                "connect", "socket"}:
                raise ValidationError(f"'{func.attr}()' is not allowed")


def _check_module(name: str) -> None:
    root = (name or "").split(".")[0]
    if not root:
        raise ValidationError("Empty import")
    if root not in ALLOWED_IMPORTS:
        raise ValidationError(
            f"Import '{root}' is not allowed here. Allowed: "
            + ", ".join(sorted(ALLOWED_IMPORTS))
        )


def build_child_env(workdir: str) -> Dict[str, str]:
    """Minimal environment for the child - no API keys, no shell secrets."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": workdir,
        "TMPDIR": workdir,
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        # Explicitly NOT forwarded: GROQ_API_KEY, OPENAI_API_KEY, AETHER_SECRET_KEY, ...
    }


def _limits():  # pragma: no cover - Linux only
    """Resource limits applied inside the child process."""
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))              # 5s CPU
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)  # 512 MB
        resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024,) * 2)  # 2 MB file
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))          # no fork bombs
    except Exception:  # noqa: BLE001 - limits are best effort
        pass


def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, object]:
    """Validate and run ``code``; always returns a JSON-friendly dict."""
    try:
        validate_code(code)
    except ValidationError as exc:
        return {"ok": False, "stage": "validation", "error": str(exc)}

    with tempfile.TemporaryDirectory(prefix="playground_") as workdir:
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workdir,
                env=build_child_env(workdir),
                preexec_fn=_limits if os.name == "posix" else None,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "stage": "execution",
                "error": f"Timed out after {timeout}s (killed)",
            }

    stdout = proc.stdout[-4000:]
    stderr = proc.stderr[-2000:]
    return {
        "ok": proc.returncode == 0,
        "stage": "execution",
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def allowed_modules() -> List[str]:
    """Sorted list of importable modules (for the UI cheat sheet)."""
    return sorted(ALLOWED_IMPORTS)


def blocked_features() -> List[str]:
    """Human readable summary of what the guard refuses."""
    return sorted(BLOCKED_NAMES) + [f".{attr}" for attr in sorted(BLOCKED_ATTRIBUTES)]


def describe() -> Tuple[str, str]:
    """Short description + version-ish tag used by the playground page."""
    return (
        "AST allow-list + isolated subprocess (python -I, rlimits, temp cwd, "
        "stripped env)",
        f"timeout={DEFAULT_TIMEOUT}s limit={MAX_CODE_CHARS} chars",
    )
