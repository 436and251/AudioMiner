from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SegmentConfig:
    target_min: float = 4.0
    target_max: float = 8.0
    hard_min: float = 3.0
    hard_max: float = 12.0
    silence_break: float = 0.7
    pad_before: float = 0.15
    pad_after: float = 0.20


@dataclass
class BuildConfig:
    output: Path
    speaker: str
    language: str = "auto"
    asr_model: str = "large-v3-turbo"
    asr_model_path: str | None = None
    asr_device: str = "auto"
    separator_model: str = "htdemucs"
    separator_device: str = "auto"
    skip_separation: bool = False
    keep_temp: bool = False
    fresh: bool = False
    min_confidence: float = 0.5
    segment: SegmentConfig = field(default_factory=SegmentConfig)
