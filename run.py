"""Local server entrypoint for Bug Triage OpenEnv."""

from __future__ import annotations

import os

import uvicorn

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional at runtime
    load_dotenv = None


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    if load_dotenv:
        load_dotenv()

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "7860"))
    reload_enabled = _as_bool(os.getenv("RELOAD", "false"))

    uvicorn.run(
        "server.app:app",
        host=host,
        port=port,
        reload=reload_enabled,
    )


if __name__ == "__main__":
    main()
