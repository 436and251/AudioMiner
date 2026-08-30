from __future__ import annotations

from pathlib import Path

from ..events import PipelineEvent, emit
from ..models import AcquiredSource
from .common import source_id


def acquire_local(value: str, *, event_sink=None, cancel_token=None) -> AcquiredSource:
    if cancel_token:
        cancel_token.raise_if_cancelled()
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"audio source not found: {path}")
    emit(event_sink, PipelineEvent("log", "source", f"Local file: {path.name}"))
    return AcquiredSource(str(path), path.name, source_id(path.name, str(path)), str(path))
