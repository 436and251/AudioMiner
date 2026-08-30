from tts_builder.config import SegmentConfig
from tts_builder.models import WordStamp
from tts_builder.segmenter import build_clips


def w(start, end, text, prob=0.9):
    return WordStamp(start=start, end=end, text=text, probability=prob)


def test_prefers_punctuation_boundary_after_minimum_duration():
    words = [
        w(0.0, 1.5, "今日は"),
        w(1.5, 3.2, "いい天気"),
        w(3.2, 4.4, "ですね。"),
        w(4.6, 6.0, "明日も"),
        w(6.0, 8.0, "晴れます。"),
    ]
    clips = build_clips(words, SegmentConfig(target_min=4.0, target_max=8.0))
    assert len(clips) == 2
    assert clips[0].text == "今日はいい天気ですね。"
    assert clips[0].end <= 4.7


def test_breaks_at_long_silence_and_merges_too_short_tail_when_possible():
    words = [
        w(0.0, 1.6, "one "),
        w(1.6, 3.4, "two "),
        w(3.4, 4.3, "three"),
        w(5.3, 6.0, " four"),
        w(6.0, 7.0, " five"),
    ]
    cfg = SegmentConfig(target_min=3.0, target_max=8.0, silence_break=0.7)
    clips = build_clips(words, cfg)
    assert len(clips) == 1
    assert clips[0].text == "one two three four five"


def test_never_emits_clip_longer_than_hard_max_for_normal_word_sequence():
    words = [w(i, i + 1.0, f"w{i} ") for i in range(15)]
    cfg = SegmentConfig(target_min=4.0, target_max=6.0, hard_max=8.0)
    clips = build_clips(words, cfg)
    assert len(clips) >= 2
    assert all(c.duration <= 8.0 for c in clips)


def test_confidence_is_mean_word_probability():
    words = [w(0.0, 2.0, "a ", 0.8), w(2.0, 4.0, "b", 0.6)]
    clips = build_clips(words, SegmentConfig(target_min=3.0, target_max=8.0))
    assert len(clips) == 1
    assert clips[0].confidence == 0.7
