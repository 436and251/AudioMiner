import json
from pathlib import Path

import numpy as np
import soundfile as sf

from tts_builder.dataset import (
    append_manifest,
    load_manifest,
    write_clip,
    write_gpt_sovits_list,
)
from tts_builder.models import ClipSpec, ManifestRecord


def test_write_clip_slices_audio_using_timestamps(tmp_path: Path):
    sr = 1000
    audio = np.arange(5000, dtype=np.float32) / 5000
    spec = ClipSpec(start=1.0, end=3.0, text="hello", confidence=0.9)
    out = tmp_path / "clip.wav"
    write_clip(audio, sr, spec, out)
    saved, saved_sr = sf.read(out, dtype="float32")
    assert saved_sr == sr
    assert len(saved) == 2000
    assert np.isclose(saved[0], audio[1000], atol=2e-4)


def test_manifest_round_trip_and_gpt_sovits_export(tmp_path: Path):
    clips = tmp_path / "clips"
    clips.mkdir()
    wav = clips / "src_0001.wav"
    sf.write(wav, np.zeros(1000, dtype=np.float32), 1000)
    record = ManifestRecord(
        clip_id="src_0001",
        audio="clips/src_0001.wav",
        source="source.mp3",
        speaker="singer_a",
        language="ja",
        start=0.2,
        end=4.3,
        text="今日はいい天気です。",
        confidence=0.91,
    )
    manifest = tmp_path / "manifest.jsonl"
    append_manifest([record], manifest)
    loaded = load_manifest(manifest)
    assert loaded == [record]

    list_path = tmp_path / "dataset.list"
    skipped = write_gpt_sovits_list(loaded, tmp_path, list_path)
    assert skipped == 0
    line = list_path.read_text(encoding="utf-8").strip()
    assert line == f"{wav.resolve()}|singer_a|ja|今日はいい天気です。"


def test_gpt_sovits_export_skips_unsupported_language(tmp_path: Path):
    record = ManifestRecord(
        clip_id="x",
        audio="clips/x.wav",
        source="x",
        speaker="a",
        language="fr",
        start=0,
        end=4,
        text="bonjour",
        confidence=0.9,
    )
    out = tmp_path / "dataset.list"
    assert write_gpt_sovits_list([record], tmp_path, out) == 1
    assert out.read_text(encoding="utf-8") == ""


def test_gpt_sovits_export_maps_regional_language_code_to_base(tmp_path: Path):
    wav = tmp_path / "clips" / "x.wav"
    wav.parent.mkdir()
    sf.write(wav, np.zeros(1000, dtype=np.float32), 1000)
    record = ManifestRecord(
        clip_id="x", audio="clips/x.wav", source="x", speaker="a",
        language="zh-cn", start=0, end=4, text="你好", confidence=0.9,
    )
    out = tmp_path / "dataset.list"
    assert write_gpt_sovits_list([record], tmp_path, out) == 0
    assert "|a|zh|你好" in out.read_text(encoding="utf-8")


def test_clip_quality_filter_uses_confidence_duration_and_text():
    from tts_builder.config import SegmentConfig
    from tts_builder.dataset import clip_is_acceptable

    cfg = SegmentConfig()
    good = ClipSpec(0, 5, "こんにちは", 0.8)
    low_conf = ClipSpec(0, 5, "こんにちは", 0.2)
    too_short = ClipSpec(0, 1, "こんにちは", 0.9)
    empty = ClipSpec(0, 5, " ", 0.9)
    assert clip_is_acceptable(good, cfg, 0.5)
    assert not clip_is_acceptable(low_conf, cfg, 0.5)
    assert not clip_is_acceptable(too_short, cfg, 0.5)
    assert not clip_is_acceptable(empty, cfg, 0.5)
