from __future__ import annotations

from collections.abc import Callable
from threading import Lock


class RunCancelledError(RuntimeError):
    pass


class WorkflowRunControl:
    _lock = Lock()
    _states: dict[int, dict[str, object]] = {}

    @classmethod
    def register_cancel_callback(cls, run_id: int, callback: Callable[[], None]) -> None:
        should_call = False
        with cls._lock:
            state = cls._states.setdefault(run_id, {"cancel_requested": False, "callback": None})
            state["callback"] = callback
            should_call = bool(state["cancel_requested"])
        if should_call:
            try:
                callback()
            except Exception:
                return

    @classmethod
    def request_cancel(cls, run_id: int) -> bool:
        callback: Callable[[], None] | None = None
        with cls._lock:
            state = cls._states.setdefault(run_id, {"cancel_requested": False, "callback": None})
            already_requested = bool(state["cancel_requested"])
            state["cancel_requested"] = True
            callback = state.get("callback")  # type: ignore[assignment]
        if callback is not None:
            try:
                callback()
            except Exception:
                return not already_requested
        return not already_requested

    @classmethod
    def is_cancel_requested(cls, run_id: int) -> bool:
        with cls._lock:
            return bool(cls._states.get(run_id, {}).get("cancel_requested"))

    @classmethod
    def clear(cls, run_id: int) -> None:
        with cls._lock:
            cls._states.pop(run_id, None)
