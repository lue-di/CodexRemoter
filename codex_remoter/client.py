from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import signal
import shutil
import socket
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import websocket


class CodexAppError(RuntimeError):
    pass


class CodexAppUnavailableError(CodexAppError):
    pass


class CodexAppTimeoutError(CodexAppError):
    pass


@dataclass
class AppTurnResult:
    message: str
    reply: str
    url: str
    target_id: str
    elapsed_ms: int


class CodexAppController:
    """Controls the Codex desktop app through its Chromium DevTools protocol.

    This intentionally targets the desktop renderer, not ``codex exec`` or
    ``codex app-server``. The app must be launched with a loopback remote-debug
    port; the controller can add that flag when it starts a managed instance.
    """

    def __init__(
        self,
        app_path: Optional[str] = None,
        codex_binary: str = "codex",
        debug_port: Optional[int] = None,
        startup_timeout: float = 30.0,
        poll_interval: float = 0.35,
        auth_file: Optional[Path] = None,
    ) -> None:
        self.app_path = app_path or self._default_app_path()
        self.codex_binary = codex_binary
        self.debug_port = debug_port
        self.startup_timeout = startup_timeout
        self.poll_interval = poll_interval
        self._launcher: Optional[subprocess.Popen[Any]] = None
        self._managed_pid: Optional[int] = None
        self._lock = asyncio.Lock()
        self.last_error: Optional[str] = None
        self.auth_file: Optional[Path] = auth_file
        self._switching_auth: bool = False
        self._auth_switch_event: Optional[asyncio.Event] = None
        self._resolved_executable: Optional[Path] = None  # 缓存找到的路径

    @staticmethod
    def _default_app_path() -> str:
        if sys_platform() == "darwin":
            return "/Applications/ChatGPT.app"
        if sys_platform() == "win32":
            # Windows 默认路径，会在 start() 中自动搜索常见位置
            localappdata = os.getenv("LOCALAPPDATA", "")
            if localappdata:
                default_path = os.path.join(localappdata, "Programs", "ChatGPT", "ChatGPT.exe")
                if os.path.exists(default_path):
                    return default_path
            return "ChatGPT.exe"
        return "codex"

    @property
    def running(self) -> bool:
        return bool(self._targets())

    def status(self) -> Dict[str, Any]:
        targets = self._targets()
        return {
            "running": bool(targets),
            "app_path": self.app_path,
            "codex_binary": self.codex_binary,
            "debug_port": self.debug_port,
            "managed_pid": self._managed_pid,
            "targets": [
                {"id": item.get("id"), "title": item.get("title"), "url": item.get("url")}
                for item in targets
            ],
            "last_error": self.last_error,
        }

    async def start(self, cwd: Optional[str] = None) -> Dict[str, Any]:
        async with self._lock:
            if self._targets():
                self.last_error = None
                if cwd:
                    await asyncio.to_thread(self._open_workspace, cwd)
                return self.status()
            if sys_platform() == "darwin":
                await asyncio.to_thread(self._quit_uninstrumented_macos_app)
                self.debug_port = self.debug_port or self._free_port()
                app = Path(self.app_path).expanduser()
                if not app.exists():
                    raise CodexAppUnavailableError("找不到 Codex App: {}".format(app))
                args = [
                    "open",
                    "-n",
                    "-a",
                    str(app),
                    "--args",
                    "--remote-debugging-address=127.0.0.1",
                    "--remote-debugging-port={}".format(self.debug_port),
                ]
                try:
                    self._launcher = subprocess.Popen(
                        args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except OSError as exc:
                    raise CodexAppUnavailableError("启动 Codex App 失败: {}".format(exc)) from exc
            else:
                # Windows 和 Linux 平台
                if sys_platform() == "win32":
                    await asyncio.to_thread(self._quit_uninstrumented_windows_app)
                self.debug_port = self.debug_port or self._free_port()
                app_path = await asyncio.to_thread(self._resolve_app_executable)

                command = [
                    str(app_path),
                    "--remote-debugging-address=127.0.0.1",
                    "--remote-debugging-port={}".format(self.debug_port),
                ]
                popen_kwargs: Dict[str, Any] = {
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL,
                }
                if sys_platform() == "win32":
                    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP，避免应用随服务退出
                    popen_kwargs["creationflags"] = 0x00000008 | 0x00000200
                else:
                    popen_kwargs["start_new_session"] = True

                try:
                    self._launcher = subprocess.Popen(command, **popen_kwargs)
                except OSError as exc:
                    raise CodexAppUnavailableError(
                        f"启动 Codex App 失败: {exc}\n应用路径: {app_path}"
                    ) from exc

            deadline = time.monotonic() + self.startup_timeout
            while time.monotonic() < deadline:
                if self._targets():
                    self._managed_pid = self._pid_for_debug_port(self.debug_port)
                    if cwd:
                        await asyncio.to_thread(self._open_workspace, cwd)
                    self.last_error = None
                    return self.status()
                await asyncio.sleep(self.poll_interval)
            raise CodexAppTimeoutError(
                "Codex App 启动超时：未发现 DevTools 页面（端口 {}）".format(self.debug_port)
            )

    async def stop(self) -> Dict[str, Any]:
        async with self._lock:
            if self._managed_pid and sys_platform() != "win32":
                with contextlib_suppress(ProcessLookupError):
                    os.killpg(self._managed_pid, signal.SIGTERM)
            elif self._launcher and self._launcher.poll() is None:
                self._launcher.terminate()
            self._launcher = None
            self._managed_pid = None
            return self.status()

    async def send_message(
        self,
        message: str,
        *,
        cwd: Optional[str] = None,
        timeout: float = 600.0,
        new_chat: bool = True,
        wait_for_reply: bool = True,
    ) -> AppTurnResult:
        if not message.strip():
            raise ValueError("message 不能为空")

        # 如果正在切换账号，等待切换完成
        if self._switching_auth:
            if self._auth_switch_event:
                try:
                    await asyncio.wait_for(
                        self._auth_switch_event.wait(),
                        timeout=self.startup_timeout + 10.0
                    )
                except asyncio.TimeoutError:
                    raise CodexAppTimeoutError(
                        "等待账号切换完成超时，请稍后重试"
                    )
            else:
                # 如果没有事件对象，简单等待一段时间
                raise CodexAppUnavailableError(
                    "Codex 正在切换账号，请稍后重试"
                )

        async with self._lock:
            has_target = bool(self._targets())
        if not has_target:
            await self.start(cwd=cwd)
        elif cwd:
            await asyncio.to_thread(self._open_workspace, cwd)
        async with self._lock:
            target = self._choose_target()
            started = time.monotonic()
            before = await asyncio.to_thread(
                self._evaluate, target, self._prepare_script(message, new_chat)
            )
            if not before.get("ok"):
                raise CodexAppError(before.get("error", "无法写入 Codex 输入框"))
            if not wait_for_reply:
                return AppTurnResult(
                    message,
                    "",
                    target.get("url", ""),
                    target.get("id", ""),
                    int((time.monotonic() - started) * 1000),
                )
            deadline = time.monotonic() + timeout
            baseline = int(before.get("assistant_count", 0))
            while time.monotonic() < deadline:
                state = await asyncio.to_thread(
                    self._evaluate, target, self._reply_script(message, baseline)
                )
                if state.get("done"):
                    return AppTurnResult(
                        message=message,
                        reply=state.get("reply", ""),
                        url=target.get("url", ""),
                        target_id=target.get("id", ""),
                        elapsed_ms=int((time.monotonic()-started)*1000),
                    )
                await asyncio.sleep(self.poll_interval)
            raise CodexAppTimeoutError("等待 Codex App 回复超过 {:.0f} 秒".format(timeout))

    def _choose_target(self) -> Dict[str, Any]:
        targets = [t for t in self._targets() if t.get("type") == "page"]
        if not targets:
            raise CodexAppUnavailableError("未找到 Codex App 页面")
        return next(
            (t for t in targets if "avatar-overlay" not in t.get("url", "")),
            targets[0],
        )

    def _targets(self) -> List[Dict[str, Any]]:
        if not self.debug_port:
            self.debug_port = self._discover_debug_port()
        if not self.debug_port:
            return []
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:{}/json/list".format(self.debug_port),
                timeout=1.5,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return []

    def _discover_debug_port(self) -> Optional[int]:
        for pid, command in self._macos_main_processes():
            del pid
            match = re.search(r"--remote-debugging-port(?:=|\s+)(\d+)", command)
            if match:
                return int(match.group(1))
        return None

    def _pid_for_debug_port(self, port: Optional[int]) -> Optional[int]:
        if not port:
            return None
        marker = re.compile(r"--remote-debugging-port(?:=|\s+){}(?:\s|$)".format(port))
        return next(
            (
                pid
                for pid, command in self._macos_main_processes()
                if marker.search(command)
            ),
            None,
        )

    def _resolve_app_executable(self) -> Path:
        """解析 Codex/ChatGPT 可执行文件的完整路径。

        优先级：缓存 > 显式配置 > PATH 命令 > 快速路径 > 深度搜索（最慢）
        """
        # 0. 使用缓存的路径（避免重复搜索）
        if self._resolved_executable and self._resolved_executable.is_file():
            return self._resolved_executable

        # 1. 用户显式指定的路径
        explicit = Path(self.app_path).expanduser()
        if explicit.is_file() and os.access(explicit, os.X_OK):
            self._resolved_executable = explicit.resolve()
            return self._resolved_executable
        # CODEX_APP_PATH 可能给的是目录，里面包含 exe
        if explicit.is_dir():
            for name in ("Codex.exe", "ChatGPT.exe", "codex", "chatgpt"):
                candidate = explicit / name
                if candidate.is_file():
                    self._resolved_executable = candidate.resolve()
                    return self._resolved_executable

        # 2. 查 PATH（针对 Codex CLI 或全局安装）
        for name in ("codex", "chatgpt", "Codex.exe", "ChatGPT.exe"):
            found = shutil.which(name)
            if found:
                self._resolved_executable = Path(found).resolve()
                return self._resolved_executable

        # 3. Windows 快速路径（不递归）
        if sys_platform() == "win32":
            fast_candidates = self._windows_fast_paths()
            for path in fast_candidates:
                if path.is_file():
                    self._resolved_executable = path.resolve()
                    return self._resolved_executable

            # 4. 深度搜索（最慢，最后尝试）
            print("正在深度搜索 WindowsApps，这可能需要几秒钟...", flush=True)
            deep_candidates = self._windows_deep_search()
            for path in deep_candidates:
                if path.is_file():
                    self._resolved_executable = path.resolve()
                    return self._resolved_executable

            # 未找到，抛出清晰的错误
            all_tried = fast_candidates + deep_candidates
            raise CodexAppUnavailableError(
                f"找不到 Codex/ChatGPT 应用。已尝试 {len(all_tried)} 个路径。\n\n"
                f"请设置 CODEX_APP_PATH 环境变量指向 Codex.exe 的完整路径。\n"
                f"如果你用微软商店安装，可以用以下命令查找：\n"
                f"  Get-ChildItem 'C:\\Program Files\\WindowsApps' -Filter '*Codex*' -Directory\n\n"
                f"找到后设置环境变量：\n"
                f"  set CODEX_APP_PATH=完整路径\\Codex.exe"
            )

        # Linux/其他平台
        raise CodexAppUnavailableError(
            f"找不到 Codex App: {self.app_path}，且未在 PATH 中发现 codex 命令"
        )

    def _windows_fast_paths(self) -> List[Path]:
        """Windows 快速路径检查（不递归，毫秒级）"""
        candidates: List[Path] = []

        # 标准安装目录
        for env_var in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            base = os.getenv(env_var)
            if not base:
                continue
            base_path = Path(base)
            for app_name in ("Codex", "ChatGPT"):
                for subdir in ("", "Programs"):
                    for exe_name in (f"{app_name}.exe", "app.exe"):
                        if subdir:
                            candidates.append(base_path / subdir / app_name / exe_name)
                        else:
                            candidates.append(base_path / app_name / exe_name)

        return candidates

    def _windows_deep_search(self) -> List[Path]:
        """Windows 深度搜索 WindowsApps（慢，仅作为兜底）"""
        candidates: List[Path] = []

        # 只搜索 C: 盘和当前系统盘，避免扫描所有驱动器
        drives_to_check = set()
        drives_to_check.add(Path("C:\\"))

        # 添加当前 Python 所在驱动器
        import sys as sys_module
        python_drive = Path(sys_module.executable).drive
        if python_drive:
            drives_to_check.add(Path(python_drive + "\\"))

        for drive in drives_to_check:
            if not drive.exists():
                continue

            for base_name in ("Program Files", "ProgramFiles"):
                windows_apps = drive / base_name / "WindowsApps"
                if not windows_apps.is_dir():
                    continue

                # 只搜索明确的 OpenAI 包名，避免通配符慢查询
                try:
                    for pattern in ("OpenAI.Codex*", "OpenAI.ChatGPT*"):
                        for pkg_dir in windows_apps.glob(pattern):
                            if not pkg_dir.is_dir():
                                continue
                            # MSIX 包常见结构
                            for exe_name in ("Codex.exe", "ChatGPT.exe", "app.exe"):
                                candidates.append(pkg_dir / "app" / exe_name)
                                candidates.append(pkg_dir / exe_name)
                except (OSError, PermissionError):
                    # WindowsApps ACL 限制
                    pass

        return candidates

    def _quit_uninstrumented_windows_app(self) -> None:
        """Windows：如果已有未带调试端口的 Codex/ChatGPT 进程，尝试正常关闭。

        注意：不检查调试端口，直接尝试关闭进程，避免死锁。
        """
        # 简单实现：用 taskkill 请求关闭同名进程
        for name in ("Codex.exe", "ChatGPT.exe"):
            try:
                subprocess.run(
                    ["taskkill", "/IM", name, "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
            except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
                pass

    def _macos_main_processes(self) -> List[tuple[int, str]]:
        if sys_platform() != "darwin":
            return []
        try:
            output = subprocess.check_output(
                ["ps", "-axo", "pid=,command="], text=True, timeout=5
            )
        except (OSError, subprocess.SubprocessError):
            return []
        rows: List[tuple[int, str]] = []
        for line in output.splitlines():
            match = re.match(r"\s*(\d+)\s+(.+)$", line)
            if not match:
                continue
            command = match.group(2)
            lower = command.lower()
            is_main = (
                "/chatgpt.app/contents/macos/chatgpt" in lower
                or "/codex.app/contents/macos/codex" in lower
            )
            if is_main and "--type=" not in lower:
                rows.append((int(match.group(1)), command))
        return rows

    def _quit_uninstrumented_macos_app(self) -> None:
        """macOS：如果已有未带调试端口的 Codex/ChatGPT 进程，请求其正常退出。"""
        for pid, command in self._macos_main_processes():
            if "--remote-debugging-port" not in command:
                try:
                    # 发送 SIGTERM 请求正常退出
                    os.kill(pid, signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    pass

    async def switch_auth(self, auth_json: Union[str, Dict[str, Any]], auto_restart: bool = False) -> Dict[str, Any]:
        """切换账号：替换 Codex 的 auth.json。

        ``auth_json`` 接受已解析的 JSON 对象，或 auth.json 的原始文本。
        ``auto_restart`` 如果为 True，会尝试重启应用（可能超时）。
        """
        payload = self._serialize_auth(auth_json)

        # 设置切换标志
        self._switching_auth = True
        self._auth_switch_event = asyncio.Event()

        try:
            # 找到 auth.json 位置
            auth_file = self._resolve_auth_file()
            if not auth_file:
                raise CodexAppError(
                    "未找到 Codex 的 auth.json。请设置 CODEX_REMOTER_AUTH_FILE 或 CODEX_HOME 环境变量"
                )

            # 备份旧的 auth.json（文件可能尚不存在）
            backup_file = auth_file.parent / (auth_file.name + ".bak")
            if auth_file.exists():
                backup_file.write_text(
                    auth_file.read_text(encoding="utf-8"), encoding="utf-8"
                )
                self.last_error = f"已备份旧 auth.json 到 {backup_file}"
            else:
                backup_file = None

            try:
                auth_file.parent.mkdir(parents=True, exist_ok=True)
                auth_file.write_text(payload, encoding="utf-8")
                self._restrict_permissions(auth_file)
                self.last_error = f"账号切换成功，已更新 {auth_file}"
            except OSError as exc:
                raise CodexAppError(f"auth.json 写入失败: {exc}") from exc

            result = {
                "ok": True,
                "message": "账号已切换，auth.json 已更新",
                "auth_file": str(auth_file),
                "backup": str(backup_file) if backup_file else None,
                "auto_restart": auto_restart,
            }

            # 可选：重启应用（默认不重启，避免超时）
            if auto_restart:
                try:
                    await self.stop()
                    await asyncio.sleep(1.0)
                    await asyncio.wait_for(self.start(), timeout=30.0)
                    result["message"] = "账号已切换，应用已重启"
                    result["restarted"] = True
                except asyncio.TimeoutError:
                    result["message"] = "账号已切换，但应用重启超时。请手动重启 Codex"
                    result["restarted"] = False
                except Exception as exc:
                    result["message"] = f"账号已切换，但应用重启失败: {exc}"
                    result["restarted"] = False
            else:
                result["message"] = "账号已切换。请手动重启 Codex 应用以生效"
                result["restarted"] = None

            return result
        finally:
            # 切换完成，设置事件并清除标志
            self._switching_auth = False
            if self._auth_switch_event:
                self._auth_switch_event.set()
                self._auth_switch_event = None

    @staticmethod
    def _serialize_auth(auth_json: Union[str, Dict[str, Any]]) -> str:
        """把请求里的 auth 内容规范化成要写入磁盘的文本。

        接受 dict（已解析的 JSON）或原始 JSON 文本；两种都会校验成合法 JSON
        对象，避免把损坏的内容写进 auth.json 之后 Codex 无法启动。
        """
        if isinstance(auth_json, str):
            text = auth_json.strip()
            if not text:
                raise CodexAppError("auth_json 不能为空")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise CodexAppError(f"auth_json 不是合法 JSON: {exc}") from exc
        else:
            parsed = auth_json

        if not isinstance(parsed, dict):
            raise CodexAppError("auth_json 必须是 JSON 对象")

        return json.dumps(parsed, ensure_ascii=False, indent=2) + "\n"

    @staticmethod
    def _restrict_permissions(path: Path) -> None:
        """尽力把 auth.json 收紧到仅所有者可读写。

        Windows 上 chmod 基本无效，忽略失败即可，不影响切换流程。
        """
        with contextlib_suppress(OSError, NotImplementedError):
            os.chmod(path, 0o600)

    def _auth_file_candidates(self) -> List[Path]:
        """Codex auth.json 的候选位置，按优先级排列。

        Codex 把凭据放在 ``$CODEX_HOME/auth.json``（默认 ``~/.codex``），三个平台
        一致；桌面 App 的 Application Support / AppData 目录只作为兜底。
        """
        home = Path.home()
        candidates: List[Path] = []

        codex_home = os.getenv("CODEX_HOME")
        if codex_home:
            candidates.append(Path(codex_home).expanduser() / "auth.json")
        candidates.append(home / ".codex" / "auth.json")

        platform = sys_platform()
        if platform == "win32":
            for env_name in ("APPDATA", "LOCALAPPDATA"):
                base = os.getenv(env_name)
                if base:
                    candidates.append(Path(base) / "Codex" / "auth.json")
                    candidates.append(Path(base) / "ChatGPT" / "auth.json")
        elif platform == "darwin":
            support = home / "Library" / "Application Support"
            candidates.append(support / "Codex" / "auth.json")
            candidates.append(support / "ChatGPT" / "auth.json")
        else:
            config = Path(os.getenv("XDG_CONFIG_HOME") or home / ".config")
            candidates.append(config / "codex" / "auth.json")

        # 去重但保持顺序
        seen: set = set()
        unique: List[Path] = []
        for candidate in candidates:
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return unique

    def _resolve_auth_file(self) -> Optional[Path]:
        """解析 Codex auth.json 路径。

        优先返回已存在的文件；都不存在时返回首选路径，让切换账号能够首次创建它。
        """
        if self.auth_file:
            return self.auth_file

        candidates = self._auth_file_candidates()
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0] if candidates else None

    def _evaluate(self, target: Dict[str, Any], expression: str) -> Dict[str, Any]:
        url = target.get("webSocketDebuggerUrl")
        if not url:
            raise CodexAppUnavailableError("Codex 页面没有 DevTools WebSocket 地址")
        try:
            ws = websocket.create_connection(url, timeout=4, suppress_origin=True)
            ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
                "expression": expression, "returnByValue": True, "awaitPromise": True,
            }}))
            while True:
                value = json.loads(ws.recv())
                if value.get("id") == 1:
                    ws.close()
                    result = value.get("result", {}).get("result", {})
                    if result.get("type") == "string":
                        return json.loads(result.get("value", "{}"))
                    return result.get("value") or {}
        except Exception as exc:
            raise CodexAppUnavailableError("CDP 调用失败: {}".format(exc)) from exc

    @staticmethod
    def _prepare_script(message: str, new_chat: bool) -> str:
        payload = json.dumps(message, ensure_ascii=False)
        return """(async () => {
          const text = %s;
          if (%s) {
            const buttons = [...document.querySelectorAll('button')];
            const newButton = buttons.find(b => {
              const label = b.getAttribute('aria-label') || b.innerText || '';
              return /new chat|新对话/i.test(label);
            });
            if (newButton && document.querySelectorAll('[data-user-message-bubble="true"]').length) {
              newButton.click();
              await new Promise(resolve => setTimeout(resolve, 500));
            }
          }

          // 尝试多种选择器查找输入框
          let box = document.querySelector('[data-codex-composer="true"]');
          if (!box) box = document.querySelector('[role="textbox"][contenteditable="true"]');
          if (!box) box = document.querySelector('textarea[placeholder*="Message"]');
          if (!box) box = document.querySelector('textarea[placeholder*="消息"]');
          if (!box) box = document.querySelector('[contenteditable="true"][role="textbox"]');
          if (!box) box = document.querySelector('div[contenteditable="true"]');
          if (!box) {
            // 最后尝试：查找所有可编辑元素
            const editable = [...document.querySelectorAll('[contenteditable="true"]')];
            box = editable.find(el => el.offsetParent !== null); // 找到可见的
          }

          if (!box) return {ok:false,error:'找不到 Codex 消息输入框。请确保 Codex 页面已完全加载。'};

          box.focus();
          await new Promise(resolve => setTimeout(resolve, 100));

          // 尝试多种方式插入文本
          let inserted = false;
          try {
            inserted = document.execCommand('insertText', false, text);
          } catch (_) {}

          if (!inserted) {
            // 如果是 textarea
            if (box.tagName === 'TEXTAREA') {
              box.value = text;
              box.dispatchEvent(new Event('input', {bubbles:true}));
            } else {
              // contenteditable div
              box.innerHTML = '<p dir="auto">' + text.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])) + '</p>';
            }
          }

          box.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:text}));
          box.dispatchEvent(new Event('change', {bubbles:true}));
          await new Promise(resolve => setTimeout(resolve, 200));

          // 查找发送按钮
          let send = document.querySelector('button[aria-label="Send"]');
          if (!send) send = document.querySelector('button[aria-label="发送"]');
          if (!send) {
            const buttons = [...document.querySelectorAll('button')];
            send = buttons.find(b => {
              const label = b.getAttribute('aria-label') || b.innerText || '';
              return /send|发送/i.test(label);
            });
          }

          if (!send || send.disabled) return {ok:false,error:'Codex 发送按钮不可用或禁用'};

          const assistantCount = document.querySelectorAll('[data-markdown-text-style="assistant-message"]').length;
          send.click();
          return {ok:true,assistant_count:assistantCount};
        })()""" % (payload, "true" if new_chat else "false")

    @staticmethod
    def _reply_script(message: str, baseline: int) -> str:
        message_json = json.dumps(message, ensure_ascii=False)
        return """(() => {
          const expected = %s;
          const users = [...document.querySelectorAll('[data-user-message-bubble="true"]')];
          const nodes = [...document.querySelectorAll('[data-markdown-text-style="assistant-message"]')];
          const reply = nodes.length ? (nodes[nodes.length - 1].innerText || '').trim() : '';
          const stop = [...document.querySelectorAll('button')].some(b => /stop|停止/i.test(b.getAttribute('aria-label') || b.innerText || ''));
          const lastUser = users.length ? (users[users.length - 1].innerText || '').trim() : '';
          const sent = lastUser === expected;
          return {done: sent && !!reply && !stop && nodes.length !== %d, reply};
        })()""" % (message_json, baseline)

    @staticmethod
    def _free_port() -> int:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def _open_workspace(self, cwd: str) -> None:
        binary = self._resolve_codex_binary()
        try:
            subprocess.run(
                [binary, "app", cwd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            details = getattr(exc, "stderr", None) or str(exc)
            raise CodexAppError("Codex App 打开工作目录失败: {}".format(details.strip())) from exc

    def _resolve_codex_binary(self) -> str:
        candidates = [
            self.codex_binary,
            "/Applications/ChatGPT.app/Contents/Resources/codex",
            "/Applications/Codex.app/Contents/Resources/codex",
        ]
        for value in candidates:
            if os.path.sep in value:
                if os.path.isfile(value) and os.access(value, os.X_OK):
                    return value
            else:
                resolved = shutil.which(value)
                if resolved:
                    return resolved
        raise CodexAppUnavailableError("找不到用于执行 `codex app PATH` 的 Codex 启动器")


def sys_platform() -> str:
    import sys
    return sys.platform


def contextlib_suppress(*exceptions: Any):
    import contextlib
    return contextlib.suppress(*exceptions)
