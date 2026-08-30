from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import ClipSpec


def write_transcript(path: Path, acquired, transcript, clips: list[ClipSpec]) -> None:
    payload = {
        "source": acquired.original,
        "label": acquired.label,
        "source_id": acquired.source_id,
        "detected_language": transcript.language,
        "language_probability": transcript.language_probability,
        "segments": [asdict(item) for item in transcript.segments],
        "words": [asdict(item) for item in transcript.words],
        "candidate_clips": [asdict(item) for item in clips],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clips_exist(output: Path, source_id: str, count: int) -> bool:
    return all(
        (output / "clips" / f"{source_id}_{index:04d}.wav").exists()
        for index in range(1, count + 1)
    )


def remove_old_clips(output: Path, source_id: str) -> None:
    clips = output / "clips"
    if clips.exists():
        for path in clips.glob(f"{source_id}_*.wav"):
            path.unlink(missing_ok=True)
