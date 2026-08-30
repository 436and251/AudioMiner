from __future__ import annotations

from pathlib import Path

from ..events import PipelineEvent, emit
from ..models import AcquiredSource
from .common import source_id


def acquire_ytdlp(url: str, temp_dir: Path, *, event_sink=None, cancel_token=None) -> AcquiredSource:
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is required for URL inputs: uv pip install yt-dlp") from exc

    def hook(data):
        if cancel_token:
            cancel_token.raise_if_cancelled()
        if data.get("status") == "downloading":
            current = data.get("downloaded_bytes")
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            emit(event_sink, PipelineEvent("stage_progress", "source", "Downloading media", current, total))

    template = str(temp_dir / "download.%(ext)s")
    options = {
        "format": "bestaudio/best", "outtmpl": template, "noplaylist": True,
        "quiet": False, "no_warnings": False, "progress_hooks": [hook],
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
    if not path.exists():
        candidates = list(temp_dir.glob("download.*"))
        if len(candidates) != 1:
            raise RuntimeError("yt-dlp finished but the downloaded audio could not be located")
        path = candidates[0]
    label = str(info.get("title") or path.name)
    return AcquiredSource(str(path), label, source_id(label, url), url)
