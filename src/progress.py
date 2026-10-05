"""Progress events for CLI and local dashboard."""

from __future__ import annotations

from typing import Any, Callable

EventCallback = Callable[[dict[str, Any]], None]


def emit(on_event: EventCallback | None, stage: str, message: str, **extra: Any) -> None:
    payload = {"stage": stage, "message": message, **extra}
    if on_event:
        on_event(payload)
