from pathlib import Path

import numpy as np
import soundfile as sf

from tts_builder.config import BuildConfig
from tts_builder.dataset import load_manifest
from tts_builder.models import AcquiredSource, TranscriptResult, TranscriptSegment, WordStamp
from tts_builder.pipeline import process_source


def test_pipeline_builds_clips_and_manifest_without_external_models(tmp_path, monkeypatch):
    source_audio = tmp_path / "source.wav"
    sf.write(source_audio, np.zeros(44100 * 10, dtype=np.float32), 44100)

    monkeypatch.setattr(
        "tts_builder.pipeline.acquire_source",
        lambda value, temp: AcquiredSource(str(source_audio), "source.wav", "source_abcd", value),
    )
    monkeypatch.setattr(
        "tts_builder.pipeline.separate_vocals", lambda path, root, **kwargs: path
    )
    monkeypatch.setattr(
        "tts_builder.pipeline.normalize_audio", lambda path, out: path
    )
    transcript = TranscriptResult(
        language="ja",
        language_probability=0.99,
        segments=[TranscriptSegment(0, 8, "こんにちは。元気です。", 0.9)],
        words=[
            WordStamp(0.2, 4.2, "こんにちは。", 0.9),
            WordStamp(5.0, 8.8, "元気です。", 0.9),
        ],
    )
    monkeypatch.setattr("tts_builder.pipeline.transcribe", lambda *args, **kwargs: transcript)

    output = tmp_path / "dataset"
    cfg = BuildConfig(output=output, speaker="target", language="ja", min_confidence=0.5)
    summary = process_source("input", cfg)

    records = load_manifest(output / "manifest.jsonl")
    assert summary.accepted == 2
    assert len(records) == 2
    assert all((output / record.audio).exists() for record in records)
    assert (output / "dataset.list").exists()
    assert (output / "transcripts" / "source_abcd.json").exists()
