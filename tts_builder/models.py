from dataclasses import dataclass

@dataclass
class WordStamp:
    start: float
    end: float
    text: str
    probability: float = 1.0

@dataclass
class ClipSpec:
    start: float
    end: float
    text: str
    confidence: float

    @property
    def duration(self) -> float:
        return self.end - self.start

@dataclass(frozen=True)
class ManifestRecord:
    clip_id: str
    audio: str
    source: str
    speaker: str
    language: str
    start: float
    end: float
    text: str
    confidence: float

@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    confidence: float

@dataclass
class TranscriptResult:
    language: str
    language_probability: float
    segments: list[TranscriptSegment]
    words: list[WordStamp]

@dataclass(frozen=True)
class AcquiredSource:
    path: str
    label: str
    source_id: str
    original: str

@dataclass(frozen=True)
class ProcessSummary:
    source_id: str
    language: str
    accepted: int
    rejected: int
