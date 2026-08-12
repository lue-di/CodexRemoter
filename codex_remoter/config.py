from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


def _as_bool(value: str, default: bool) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    app_path: str = "/Applications/ChatGPT.app"
    codex_binary: str = "codex"
    debug_port: Optional[int] = None
    host: str = "127.0.0.1"
    port: int = 8000
    api_key: Optional[str] = None
    autostart: bool = True
    startup_timeout_seconds: float = 30.0
    max_message_timeout_seconds: float = 3600.0
    default_cwd: Optional[str] = None
    allowed_roots: List[Path] = field(default_factory=list)
    auth_file: Optional[Path] = None

    @classmethod
    def from_env(cls) -> "Settings":
        roots = os.getenv("CODEX_REMOTER_ALLOWED_ROOTS", "")
        auth_file = os.getenv("CODEX_REMOTER_AUTH_FILE")
        if auth_file:
            auth_file = Path(auth_file).expanduser().resolve()

        # 根据平台设置默认应用路径
        import sys
        if sys.platform == "darwin":
            default_app_path = "/Applications/ChatGPT.app"
        elif sys.platform == "win32":
            localappdata = os.getenv("LOCALAPPDATA", "")
            default_app_path = os.path.join(localappdata, "Programs", "ChatGPT", "ChatGPT.exe") if localappdata else "ChatGPT.exe"
        else:
            default_app_path = "codex"

        return cls(
            app_path=os.getenv("CODEX_APP_PATH", default_app_path),
            codex_binary=os.getenv("CODEX_BINARY", "codex"),
            debug_port=int(os.getenv("CODEX_DEBUG_PORT", "0")) or None,
            host=os.getenv("CODEX_REMOTER_HOST", "0.0.0.0"),
            port=int(os.getenv("CODEX_REMOTER_PORT", "9987")),
            api_key=os.getenv("CODEX_REMOTER_API_KEY") or None,
            autostart=_as_bool(os.getenv("CODEX_REMOTER_AUTOSTART", "true"), True),
            startup_timeout_seconds=float(os.getenv("CODEX_REMOTER_STARTUP_TIMEOUT", "30")),
            max_message_timeout_seconds=float(os.getenv("CODEX_REMOTER_MAX_MESSAGE_TIMEOUT", "3600")),
            default_cwd=os.getenv("CODEX_REMOTER_DEFAULT_CWD") or None,
            allowed_roots=[Path(x).expanduser().resolve() for x in roots.split(os.pathsep) if x.strip()],
            auth_file=auth_file,
        )

    def resolve_cwd(self, value: Optional[str]) -> Optional[str]:
        path_value = value or self.default_cwd
        if not path_value:
            return None
        path = Path(path_value).expanduser().resolve()
        if not path.is_dir():
            raise ValueError("工作目录不存在或不是目录: {}".format(path))
        if self.allowed_roots and not any(path == root or root in path.parents for root in self.allowed_roots):
            raise ValueError("工作目录不在 CODEX_REMOTER_ALLOWED_ROOTS 白名单中")
        return str(path)
