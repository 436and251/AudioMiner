from __future__ import annotations

import subprocess
from pathlib import Path

from .sources.common import is_url, source_id
from .runtime import resolve_binary
from .sources.router import acquire_source

__all__ = ["acquire_source", "is_url", "normalize_audio", "source_id"]


def require_ffmpeg() -> str:
    return resolve_binary("ffmpeg")


def normalize_audio(input_path: Path, output_path: Path, sample_rate: int = 44100) -> Path:
    """Decode to a mono PCM16 WAV once, so downstream slicing stays simple."""
    ffmpeg = require_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(input_path), "-vn", "-ac", "1", "-ar", str(sample_rate),
        "-c:a", "pcm_s16le", str(output_path),
    ]
    subprocess.run(command, check=True)
    return output_path
