"""Backwards-compatible facade.

The implementation now lives in :mod:`src.utils.code_sandbox` so that the API
(``src/api/routes/sandbox.py``) and the playground share exactly one guard.
"""

from src.utils.code_sandbox import *  # noqa: F401,F403
from src.utils.code_sandbox import (  # noqa: F401  (explicit, for IDEs)
    ALLOWED_IMPORTS,
    BLOCKED_ATTRIBUTES,
    BLOCKED_NAMES,
    DEFAULT_TIMEOUT,
    MAX_AST_NODES,
    MAX_CODE_CHARS,
    ValidationError,
    allowed_modules,
    blocked_features,
    build_child_env,
    describe,
    run_python,
    validate_code,
)
