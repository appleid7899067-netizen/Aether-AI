"""
API routes package.

Modules are imported lazily by the application (see ``src.api.main``) so that a
single optional/heavy dependency (GUI automation, OCR, ...) cannot prevent the
whole API from booting.
"""

__all__ = [
    "autonomous",
    "bugbounty",
    "bugbounty_auto",
    "chat",
    "control",
    "desktop",
    "developer",
    "discord",
    "evolution",
    "intelligence",
    "live_testing",
    "memory",
    "monitor",
    "n8n",
    "openclaw",
    "plugins",
    "proactive",
    "security",
    "settings",
    "tasks",
    "v3",
    "vision",
    "voice",
    "voice_commands",
    "workflows",
]
