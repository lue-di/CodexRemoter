from __future__ import annotations

import pytest

from codex_remoter.client import (
    CodexAppConnectionError,
    CodexAppController,
    CodexAppUnavailableError,
)


TARGET = {
    "id": "page-1",
    "type": "page",
    "url": "app://-/index.html",
    "webSocketDebuggerUrl": "ws://127.0.0.1:1/devtools/page/page-1",
}


class DelayedReadyController(CodexAppController):
    def __init__(self) -> None:
        super().__init__(debug_port=1, startup_timeout=0.2, poll_interval=0.001)
        self.probes = 0

    def _targets(self):
        return [TARGET]

    def _evaluate(self, target, expression):
        self.probes += 1
        if self.probes < 3:
            raise CodexAppUnavailableError("CDP 调用失败: [Errno 111] Connection refused")
        return {"ok": True}


class FakeLauncher:
    def __init__(self, controller: "DelayedStopController") -> None:
        self.controller = controller

    def poll(self):
        return None

    def terminate(self):
        self.controller.termination_requested = True


class DelayedStopController(CodexAppController):
    def __init__(self) -> None:
        super().__init__(debug_port=1, startup_timeout=0.2, poll_interval=0.001)
        self.termination_requested = False
        self.polls_after_terminate = 0
        self._launcher = FakeLauncher(self)

    def _targets(self):
        if not self.termination_requested:
            return [TARGET]
        self.polls_after_terminate += 1
        return [TARGET] if self.polls_after_terminate < 3 else []


@pytest.mark.anyio
async def test_ready_target_retries_connection_refused():
    controller = DelayedReadyController()

    target = await controller._wait_for_ready_target()

    assert target == TARGET
    assert controller.probes == 3


class ConnectionDropsAfterProbeController(CodexAppController):
    def __init__(self) -> None:
        super().__init__(debug_port=1, startup_timeout=0.2, poll_interval=0.001)
        self.calls = 0

    def _targets(self):
        return [TARGET]

    def _evaluate(self, target, expression):
        self.calls += 1
        if self.calls == 2:
            raise CodexAppConnectionError(
                "CDP 建连失败: [Errno 111] Connection refused"
            )
        if "assistant_count" in expression:
            return {"ok": True, "assistant_count": 0}
        return {"ok": True}


@pytest.mark.anyio
async def test_send_retries_if_connection_drops_after_ready_probe():
    controller = ConnectionDropsAfterProbeController()

    result = await controller.send_message("hello", wait_for_reply=False)

    assert result.message == "hello"
    assert controller.calls == 4


@pytest.mark.anyio
async def test_stop_waits_until_old_debug_listener_is_gone():
    controller = DelayedStopController()

    status = await controller.stop()

    assert status["running"] is False
    assert controller.polls_after_terminate >= 3
    assert controller._launcher is None


class InterruptedReplyController(CodexAppController):
    def __init__(self, states) -> None:
        super().__init__(debug_port=1, startup_timeout=0.2, poll_interval=0.001)
        self.states = iter(states)

    def _targets(self):
        return [TARGET]

    def _evaluate(self, target, expression):
        if "has_new_reply" in expression:
            return next(self.states)
        if "assistant_count" in expression:
            return {"ok": True, "assistant_count": 0}
        return {"ok": True}


@pytest.mark.anyio
async def test_send_returns_when_generation_is_interrupted_without_reply():
    controller = InterruptedReplyController([
        {"generating": True, "has_new_reply": False, "reply": ""},
        {"generating": False, "has_new_reply": False, "reply": ""},
    ])

    result = await controller.send_message("hello")

    assert result.status == "interrupted"
    assert result.reply == ""


@pytest.mark.anyio
async def test_send_returns_partial_reply_after_manual_stop():
    controller = InterruptedReplyController([
        {"generating": True, "has_new_reply": True, "reply": "partial"},
        {"generating": False, "has_new_reply": True, "reply": "partial"},
    ])

    result = await controller.send_message("hello")

    assert result.status == "completed"
    assert result.reply == "partial"
