from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Union

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from .client import (
    CodexAppController,
    CodexAppError,
    CodexAppTimeoutError,
    CodexAppUnavailableError,
)
from .config import Settings


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartRequest(StrictModel):
    cwd: Optional[str] = None


class AuthRequest(BaseModel):
    """切换账号请求，直接传 Codex 的 auth.json 内容（无需 base64）。

    两种写法都支持：

    - ``{"auth_json": {...}}`` —— 包一层；也接受 auth.json 的原始文本
    - 直接把 auth.json 的内容作为请求体
    """

    model_config = ConfigDict(extra="allow")

    auth_json: Optional[Union[Dict[str, Any], str]] = None
    auto_restart: bool = False  # 是否自动重启应用（默认不重启，避免超时）

    def resolved_auth(self) -> Union[Dict[str, Any], str]:
        if self.auth_json is not None:
            if isinstance(self.auth_json, str) and not self.auth_json.strip():
                raise ValueError("auth_json 不能为空")
            return self.auth_json
        extra = self.model_extra or {}
        if not extra:
            raise ValueError(
                "请求体不能为空：请直接传 auth.json 内容，或使用 auth_json 字段"
            )
        return extra


class MessageRequest(StrictModel):
    message: str = Field(..., min_length=1)
    cwd: Optional[str] = None
    timeout_seconds: float = Field(600.0, gt=0)
    new_chat: bool = True
    wait_for_reply: bool = True


def create_app(
    settings: Optional[Settings] = None,
    controller: Optional[CodexAppController] = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    controller = controller or CodexAppController(
        app_path=settings.app_path,
        codex_binary=settings.codex_binary,
        debug_port=settings.debug_port,
        startup_timeout=settings.startup_timeout_seconds,
        auth_file=settings.auth_file,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.settings = settings
        application.state.codex_app = controller
        if settings.autostart:
            try:
                await controller.start(cwd=settings.default_cwd)
            except CodexAppError as exc:
                controller.last_error = str(exc)
        try:
            yield
        finally:
            # Do not close an app the API did not launch itself.
            if controller._launcher is not None:
                await controller.stop()

    application = FastAPI(
        title="Codex App Remoter API", version="0.1.0", lifespan=lifespan
    )

    async def require_api_key(
        authorization: Optional[str] = Header(None),
        x_api_key: Optional[str] = Header(None),
    ) -> None:
        if not settings.api_key:
            return
        bearer = (
            authorization[7:].strip()
            if authorization and authorization.lower().startswith("bearer ")
            else ""
        )
        supplied = x_api_key or bearer
        if not supplied or not secrets.compare_digest(supplied, settings.api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 无效"
            )

    auth = Depends(require_api_key)

    @application.get("/")
    async def root() -> Dict[str, Any]:
        return {"name": "Codex App Remoter", "docs": "/docs", "health": "/health"}

    @application.get("/health")
    async def health(_: Request) -> Dict[str, Any]:
        info = controller.status()
        return {"ok": info["running"], "codex_app": info}

    @application.post("/v1/codex-app/start", dependencies=[auth])
    async def start(body: StartRequest = StartRequest()) -> Dict[str, Any]:
        await _call(controller.start(cwd=_cwd(settings, body.cwd)))
        return controller.status()

    @application.post("/v1/codex-app/stop", dependencies=[auth])
    async def stop() -> Dict[str, Any]:
        return await _call(controller.stop())

    @application.post("/v1/codex-app/restart", dependencies=[auth])
    async def restart(body: StartRequest = StartRequest()) -> Dict[str, Any]:
        await _call(controller.stop())
        await _call(controller.start(cwd=_cwd(settings, body.cwd)))
        return controller.status()

    @application.post("/v1/codex-app/messages", dependencies=[auth])
    async def send_message(body: MessageRequest) -> Dict[str, Any]:
        timeout = min(body.timeout_seconds, settings.max_message_timeout_seconds)
        if body.timeout_seconds > settings.max_message_timeout_seconds:
            raise HTTPException(status_code=400, detail="timeout_seconds 超出服务端上限")
        result = await _call(
            controller.send_message(
                body.message,
                cwd=_cwd(settings, body.cwd),
                timeout=timeout,
                new_chat=body.new_chat,
                wait_for_reply=body.wait_for_reply,
            )
        )
        return {
            "message": result.message,
            "reply": result.reply,
            "elapsed_ms": result.elapsed_ms,
            "target_id": result.target_id,
            "url": result.url,
        }

    @application.post("/v1/codex-app/auth", dependencies=[auth])
    async def switch_account(body: AuthRequest) -> Dict[str, Any]:
        try:
            payload = body.resolved_auth()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        result = await _call(controller.switch_auth(payload, auto_restart=body.auto_restart))
        return result

    return application


def _cwd(settings: Settings, value: Optional[str]) -> Optional[str]:
    try:
        return settings.resolve_cwd(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _call(awaitable: Any) -> Any:
    try:
        return await awaitable
    except CodexAppTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except CodexAppUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CodexAppError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


app = create_app()
