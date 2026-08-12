from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from codex_remoter.api import create_app
from codex_remoter.client import (
    AppTurnResult,
    CodexAppController,
    CodexAppTimeoutError,
)
from codex_remoter.config import Settings


class FakeController(CodexAppController):
    def __init__(self) -> None:
        super().__init__(debug_port=1, startup_timeout=0.01)
        self.started = False
        self.messages = []

    @property
    def running(self):
        return self.started

    def status(self):
        return {"running": self.started, "debug_port": 1, "targets": [], "last_error": None}

    async def start(self, cwd=None):
        self.started = True
        return self.status()

    async def stop(self):
        self.started = False
        return self.status()

    async def send_message(self, message, **kwargs):
        self.messages.append((message, kwargs))
        return AppTurnResult(message, "fake reply", "app://-/index.html", "target", 1)


@pytest.mark.anyio
async def test_health_and_message_api(tmp_path: Path):
    fake = FakeController()
    app = create_app(
        Settings(autostart=False, default_cwd=str(tmp_path)),
        controller=fake,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/health")).json()["ok"] is False
        response = await client.post("/v1/codex-app/messages", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json()["reply"] == "fake reply"
        assert response.json()["status"] == "completed"
        assert fake.messages[0][0] == "hello"


@pytest.mark.anyio
async def test_api_key_and_cwd_validation(tmp_path: Path):
    fake = FakeController()
    app = create_app(
        Settings(autostart=False, api_key="secret", default_cwd=str(tmp_path)),
        controller=fake,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/v1/codex-app/stop")).status_code == 401
        assert (
            await client.post(
                "/v1/codex-app/stop", headers={"X-API-Key": "secret"}
            )
        ).status_code == 200
        invalid = await client.post(
            "/v1/codex-app/messages",
            headers={"X-API-Key": "secret"},
            json={"message": "hello", "cwd": str(tmp_path / "missing")},
        )
        assert invalid.status_code == 400


@pytest.mark.anyio
async def test_stop_timeout_is_reported_as_gateway_timeout():
    fake = FakeController()

    async def timeout():
        raise CodexAppTimeoutError("Codex App 停止超时")

    fake.stop = timeout
    app = create_app(Settings(autostart=False), controller=fake)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/codex-app/stop")

    assert response.status_code == 504
    assert response.json()["detail"] == "Codex App 停止超时"
