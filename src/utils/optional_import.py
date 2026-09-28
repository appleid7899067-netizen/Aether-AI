"""Optional imports for desktop-only dependencies.

Aether AI is a desktop assistant: many modules import GUI/audio packages such as
``pyautogui``, ``pynput``, ``pyaudio`` or ``sounddevice``.  Those packages either
cannot be installed or raise on import when there is no graphical session (for
example inside Docker or on a Render/Fly/Heroku dyno).

``optional_import`` keeps the import working on a headless server by returning a
proxy object instead of the real module:

* reading an attribute returns another proxy (or a known constant, see below),
* *assigning* an attribute is accepted and ignored (``pyautogui.FAILSAFE = True``),
* *calling* anything raises :class:`MissingDependency` with an actionable message.

That way the API boots and every non-GUI feature (chat, memory, voice synthesis,
bug-bounty recon, ...) keeps working; only the desktop-control calls fail, with a
clear error instead of an ``ImportError`` at startup.
"""
from __future__ import annotations

import importlib
from typing import Any, Dict, Optional

__all__ = ["MissingDependency", "optional_import", "is_available"]


class MissingDependency(RuntimeError):
    """Raised when a desktop-only dependency is used on a headless machine."""


# Well known integer constants of the optional packages.  They are needed at
# import time (for example ``AudioConfig.FORMAT = pyaudio.paInt16``), so we expose
# the real values instead of proxies.
_KNOWN_CONSTANTS: Dict[str, Dict[str, Any]] = {
    "pyaudio": {
        "paInt8": 16,
        "paUInt8": 32,
        "paInt16": 8,
        "paInt24": 4,
        "paInt32": 2,
        "paFloat32": 1,
        "paContinue": 0,
        "paComplete": 1,
        "paAbort": 2,
        "paNoError": 0,
        "paInputOverflowed": 0x00000002,
        "paOutputUnderflowed": 0x00000004,
        "paNotInitialized": -10000,
    },
}


class _UnavailableModule:
    """Proxy that raises only when the missing dependency is actually used."""

    def __init__(self, name: str, error: Optional[BaseException] = None, hint: str = ""):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_error", error)
        object.__setattr__(self, "_hint", hint)

    # -- helpers ---------------------------------------------------------
    def _message(self) -> str:
        root = self._name.split(".")[0]
        detail = f" ({self._error})" if self._error else ""
        hint = f" {self._hint}" if self._hint else ""
        return (
            f"'{root}' is not available in this environment{detail}. "
            f"This feature requires a full desktop installation of Aether AI.{hint}"
        )

    def _raise(self):
        raise MissingDependency(self._message())

    # -- attribute protocol ----------------------------------------------
    def __getattr__(self, item: str):
        root = object.__getattribute__(self, "_name").split(".")[0]
        constants = _KNOWN_CONSTANTS.get(root, {})
        if item in constants:
            return constants[item]
        if item.startswith("__") and item.endswith("__"):
            raise AttributeError(item)
        return _UnavailableModule(
            f"{object.__getattribute__(self, '_name')}.{item}",
            object.__getattribute__(self, "_error"),
            object.__getattribute__(self, "_hint"),
        )

    def __setattr__(self, key: str, value: Any) -> None:
        # ``pyautogui.FAILSAFE = True`` and friends are no-ops on a headless host.
        object.__setattr__(self, f"_set_{key}", value)

    # -- call protocol ----------------------------------------------------
    def __call__(self, *args, **kwargs):
        self._raise()

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<unavailable module '{object.__getattribute__(self, '_name')}'>"


def optional_import(module_name: str, hint: str = "", package: Optional[str] = None):
    """Import ``module_name`` or return a proxy that fails on first use."""
    try:
        return importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - any import failure degrades gracefully
        return _UnavailableModule(module_name, exc, hint)


def is_available(module_name: str) -> bool:
    """Return ``True`` when ``module_name`` can really be imported here."""
    try:
        importlib.import_module(module_name)
        return True
    except Exception:  # noqa: BLE001
        return False
