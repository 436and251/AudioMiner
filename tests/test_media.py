from pathlib import Path

from tts_builder.media import is_url, source_id
from tts_builder.transcriber import normalize_language


def test_url_detection_handles_http_and_local_paths():
    assert is_url("https://www.youtube.com/watch?v=abc")
    assert is_url("https://www.bilibili.com/video/BV123")
    assert not is_url("audio/interview.m4a")
    assert not is_url("C:/audio/interview.wav")


def test_source_id_is_readable_stable_and_filesystem_safe():
    first = source_id("日本語 interview #1.m4a", "same-source")
    second = source_id("日本語 interview #1.m4a", "same-source")
    assert first == second
    assert first.startswith("interview_1_")
    assert len(first) <= 64
    assert all(ch.isalnum() or ch in "_-" for ch in first)


def test_language_auto_maps_to_none_and_codes_are_normalized():
    assert normalize_language("auto") is None
    assert normalize_language("JA") == "ja"
    assert normalize_language("zh-CN") == "zh-cn"


def test_asr_language_uses_whisper_base_language_code():
    from tts_builder.transcriber import asr_language

    assert asr_language("auto") is None
    assert asr_language("zh-CN") == "zh"
    assert asr_language("ja-JP") == "ja"
