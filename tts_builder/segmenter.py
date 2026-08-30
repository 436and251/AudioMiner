from __future__ import annotations

from statistics import fmean

from .config import SegmentConfig
from .models import ClipSpec, WordStamp

_TERMINAL = (".", "?", "!", "。", "？", "！")


def _duration(words: list[WordStamp]) -> float:
    return words[-1].end - words[0].start


def _should_break_before(
    group: list[WordStamp], next_word: WordStamp, cfg: SegmentConfig
) -> bool:
    if not group:
        return False
    duration = _duration(group)
    gap = max(0.0, next_word.start - group[-1].end)
    if duration >= cfg.target_min and group[-1].text.rstrip().endswith(_TERMINAL):
        return True
    if duration >= cfg.target_min and gap >= cfg.silence_break:
        return True
    projected = next_word.end - group[0].start
    return duration >= cfg.hard_min and projected > cfg.target_max


def _initial_groups(words: list[WordStamp], cfg: SegmentConfig) -> list[list[WordStamp]]:
    groups: list[list[WordStamp]] = []
    current: list[WordStamp] = []
    for word in words:
        if current and _should_break_before(current, word, cfg):
            groups.append(current)
            current = []
        current.append(word)
        if _duration(current) >= cfg.hard_max:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _can_merge(left: list[WordStamp], right: list[WordStamp], cfg: SegmentConfig) -> bool:
    return right[-1].end - left[0].start <= cfg.hard_max


def _merge_short_groups(
    groups: list[list[WordStamp]], cfg: SegmentConfig
) -> list[list[WordStamp]]:
    merged: list[list[WordStamp]] = []
    index = 0
    while index < len(groups):
        group = groups[index]
        if _duration(group) >= cfg.hard_min:
            merged.append(group)
            index += 1
            continue
        if index + 1 < len(groups) and _can_merge(group, groups[index + 1], cfg):
            merged.append(group + groups[index + 1])
            index += 2
            continue
        if merged and _can_merge(merged[-1], group, cfg):
            merged[-1].extend(group)
        else:
            merged.append(group)
        index += 1
    return merged


def _to_clip(words: list[WordStamp], cfg: SegmentConfig) -> ClipSpec:
    text = "".join(word.text for word in words).strip()
    return ClipSpec(
        start=max(0.0, words[0].start - cfg.pad_before),
        end=words[-1].end + cfg.pad_after,
        text=text,
        confidence=fmean(word.probability for word in words),
    )


def build_clips(words: list[WordStamp], config: SegmentConfig) -> list[ClipSpec]:
    """Group timestamped words into TTS-friendly utterances."""
    valid = [word for word in words if word.end > word.start and word.text.strip()]
    if not valid:
        return []
    groups = _merge_short_groups(_initial_groups(valid, config), config)
    return [_to_clip(group, config) for group in groups if "".join(w.text for w in group).strip()]
