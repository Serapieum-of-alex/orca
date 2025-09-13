from __future__ import annotations

from typing import Callable, List

from ..core.events import Event


_EVENT_HANDLERS: List[Callable[[Event], None]] = []


def on_event(handler: Callable[[Event], None]) -> None:
    _EVENT_HANDLERS.append(handler)


def get_event_handlers() -> List[Callable[[Event], None]]:
    return list(_EVENT_HANDLERS)


__all__ = ["on_event", "get_event_handlers"]
