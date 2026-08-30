from __future__ import annotations

from pathlib import Path
from statistics import fmean

from .events import CancellationToken, EventSink, PipelineEvent, emit
from .models import TranscriptResult, TranscriptSegment, WordStamp


def normalize_language(language: str) -> str | None:
    value = language.strip().lower()
    return None if value == "auto" else value


def asr_language(language: str) -> str | None:
    normalized = normalize_language(language)
    return None if normalized is None else normalized.split("-", 1)[0]


def _resolve_device(device: str) -> tuple[str, str]:
    if device != "auto":
        return device, "float16" if device == "cuda" else "int8"
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def _audio_duration(path: Path) -> float | None:
    try:
        import soundfile as sf
        return float(sf.info(path).duration)
    except Exception:
        return None


def transcribe(audio_path: Path, model_name: str = "large-v3-turbo", language: str = "auto",
               device: str = "auto", *, event_sink: EventSink | None = None,
               cancel_token: CancellationToken | None = None) -> TranscriptResult:
    """Transcribe multilingual speech with VAD and word timestamps."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is required: pip install faster-whisper") from exc

    if cancel_token:
        cancel_token.raise_if_cancelled()
    resolved_device, compute_type = _resolve_device(device)
    emit(event_sink, PipelineEvent("log", "asr", f"Loading {model_name} on {resolved_device}"))
    model = WhisperModel(model_name, device=resolved_device, compute_type=compute_type)
    raw_segments, info = model.transcribe(
        str(audio_path), language=asr_language(language), task="transcribe", beam_size=5,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 500},
        word_timestamps=True, condition_on_previous_text=False,
    )
    duration = _audio_duration(audio_path)
    segments: list[TranscriptSegment] = []
    words: list[WordStamp] = []
    for segment in raw_segments:
        if cancel_token:
            cancel_token.raise_if_cancelled()
        segment_words: list[WordStamp] = []
        for word in segment.words or []:
            stamp = WordStamp(float(word.start), float(word.end), str(word.word), float(word.probability or 0.0))
            words.append(stamp)
            segment_words.append(stamp)
        confidence = fmean(w.probability for w in segment_words) if segment_words else 0.0
        segments.append(TranscriptSegment(float(segment.start), float(segment.end), str(segment.text).strip(), confidence))
        emit(event_sink, PipelineEvent(
            "stage_progress", "asr", str(segment.text).strip(), float(segment.end), duration,
            {"language": str(info.language)},
        ))
    return TranscriptResult(str(info.language), float(info.language_probability), segments, words)
