"""Codex Remoter ASGI entry point."""

import uvicorn

from codex_remoter.api import app
from codex_remoter.config import Settings


if __name__ == "__main__":
    settings = Settings.from_env()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
