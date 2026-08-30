from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import soundfile as sf

from .models import ClipSpec, ManifestRecord

GPT_SOVITS_LANGUAGES = {"zh", "ja", "en", "ko", "yue"}


def _gpt_language(language: str) -> str | None:
    value = language.lower()
    if value in GPT_SOVITS_LANGUAGES:
        return value
    base = value.split("-", 1)[0]
    return base if base in GPT_SOVITS_LANGUAGES else None


def clip_is_acceptable(
    clip: ClipSpec, config, min_confidence: float, min_text_chars: int = 2
) -> bool:
    text = clip.text.strip()
    return (
        config.hard_min <= clip.duration <= config.hard_max
        and len(text) >= min_text_chars
        and clip.confidence >= min_confidence
    )


def write_clip(
    audio: np.ndarray,
    sample_rate: int,
    clip: ClipSpec,
    output_path: Path,
) -> None:
    """Write one clip from an in-memory mono waveform as PCM16 WAV."""
    start = max(0, round(clip.start * sample_rate))
    end = min(len(audio), round(clip.end * sample_rate))
    if end <= start:
        raise ValueError(f"invalid clip interval: {clip.start:.3f}-{clip.end:.3f}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, audio[start:end], sample_rate, subtype="PCM_16")


def append_manifest(records: list[ManifestRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def load_manifest(path: Path) -> list[ManifestRecord]:
    if not path.exists():
        return []
    records: list[ManifestRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(ManifestRecord(**json.loads(line)))
    return records


def write_gpt_sovits_list(
    records: list[ManifestRecord],
    dataset_root: Path,
    output_path: Path,
) -> int:
    """Export supported records; return the number skipped by language."""
    lines: list[str] = []
    skipped = 0
    for record in records:
        language = _gpt_language(record.language)
        if language is None:
            skipped += 1
            continue
        audio_path = (dataset_root / record.audio).resolve()
        lines.append(
            f"{audio_path}|{record.speaker}|{language}|{record.text}"
        )
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return skipped


def replace_source_manifest(
    records: list[ManifestRecord], path: Path, source_id: str
) -> None:
    """Replace one source's records without duplicating previous reruns."""
    prefix = f"{source_id}_"
    kept = [record for record in load_manifest(path) if not record.clip_id.startswith(prefix)]
    combined = [*kept, *records]
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for record in combined:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    temp.replace(path)
