from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from ..models import AcquiredSource
from .bilibili import acquire_bilibili
from .common import is_url
from .local import acquire_local
from .ytdlp import acquire_ytdlp


def is_bilibili_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "b23.tv" or host == "bilibili.com" or host.endswith(".bilibili.com")


def _call(func, *args, event_sink=None, cancel_token=None):
    if event_sink is None and cancel_token is None:
        return func(*args)
    return func(*args, event_sink=event_sink, cancel_token=cancel_token)


def acquire_source(value: str, temp_dir: Path, *, event_sink=None, cancel_token=None) -> AcquiredSource:
    if not is_url(value):
        return _call(acquire_local, value, event_sink=event_sink, cancel_token=cancel_token)
    if is_bilibili_url(value):
        return _call(acquire_bilibili, value, temp_dir, event_sink=event_sink, cancel_token=cancel_token)
    return _call(acquire_ytdlp, value, temp_dir, event_sink=event_sink, cancel_token=cancel_token)
