from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event
from typing import Callable


@dataclass(frozen=True)
class PipelineEvent:
    kind: str
    stage: str | None = None
    message: str = ""
    current: float | None = None
    total: float | None = None
    metadata: dict = field(default_factory=dict)


EventSink = Callable[[PipelineEvent], None]


class PipelineCancelled(RuntimeError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise PipelineCancelled("task cancelled")


def emit(sink: EventSink | None, event: PipelineEvent) -> None:
    if sink is not None:
        sink(event)
