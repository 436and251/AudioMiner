from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import soundfile as sf

from .cache import PipelineCache, source_identity
from .config import BuildConfig
from .dataset import clip_is_acceptable, load_manifest, replace_source_manifest, write_clip, write_gpt_sovits_list
from .events import CancellationToken, EventSink, PipelineCancelled, PipelineEvent, emit
from .media import acquire_source, normalize_audio
from .models import ManifestRecord, ProcessSummary
from .pipeline_output import clips_exist, remove_old_clips, write_transcript
from .segmenter import build_clips
from .separator import separate_vocals
from .transcriber import normalize_language, transcribe


def _effective_language(requested: str, detected: str) -> str:
    return normalize_language(requested) or detected.lower()


def _emit(sink: EventSink | None, kind: str, stage: str | None = None,
          message: str = "", current=None, total=None, **metadata) -> None:
    emit(sink, PipelineEvent(kind, stage, message, current, total, metadata))


def _check(token: CancellationToken | None) -> None:
    if token:
        token.raise_if_cancelled()


def _run_stage(cache: PipelineCache, cache_name: str, signature: str, action, *,
               view_name: str | None = None, sink=None, token=None):
    view = view_name or cache_name
    _check(token)
    cache.begin(cache_name, signature)
    _emit(sink, "stage_started", view)
    try:
        result = action()
        _check(token)
    except PipelineCancelled:
        _emit(sink, "pipeline_cancelled", view, "Cancelled")
        raise
    except Exception as exc:
        cache.fail(cache_name, signature, exc)
        _emit(sink, "stage_failed", view, str(exc))
        raise
    _emit(sink, "stage_completed", view)
    return result


def _acquire(source, cache, signature, sink=None, token=None):
    cached = cache.load_acquired(signature)
    if cached:
        print(f"[cache] source audio hit: {cached.path}", flush=True)
        _emit(sink, "stage_cache_hit", "source", "Cached source audio")
        return cached
    def acquire_action():
        if sink is None and token is None:
            return acquire_source(source, cache.source_dir)
        return acquire_source(source, cache.source_dir, event_sink=sink, cancel_token=token)
    acquired = _run_stage(
        cache, "acquire", signature, acquire_action,
        view_name="source", sink=sink, token=token,
    )
    cache.save_acquired(signature, acquired)
    return acquired


def _ensure_normalized(acquired, config, cache, sep_sig, norm_sig, sink=None, token=None):
    input_audio = Path(acquired.path)
    sep_stage = cache.stage_data("separate")
    sep_path = Path(sep_stage.get("path", "")) if sep_stage.get("path") else None
    if sep_path and not sep_path.is_absolute():
        sep_path = cache.root / sep_path

    if config.skip_separation:
        vocals = input_audio
        if cache.stage_hit("separate", sep_sig, vocals):
            _emit(sink, "stage_cache_hit", "separate", "Separation skipped")
        else:
            cache.complete("separate", sep_sig, path=str(vocals))
            _emit(sink, "stage_completed", "separate", "Separation skipped")
    elif cache.stage_hit("separate", sep_sig, sep_path):
        vocals = sep_path
        print("[cache] separated vocals hit", flush=True)
        _emit(sink, "stage_cache_hit", "separate", "Cached vocals")
    else:
        def separate_action():
            kwargs = {"model": config.separator_model, "device": config.separator_device}
            if sink is not None or token is not None:
                kwargs.update(event_sink=sink, cancel_token=token)
            return separate_vocals(input_audio, cache.root / "separated", **kwargs)
        vocals = _run_stage(cache, "separate", sep_sig, separate_action, sink=sink, token=token)
        try:
            stored = vocals.resolve().relative_to(cache.root.resolve()).as_posix()
        except ValueError:
            stored = str(vocals.resolve())
        cache.complete("separate", sep_sig, path=stored)

    if cache.stage_hit("normalize", norm_sig, cache.normalized_path):
        print("[cache] normalized audio hit", flush=True)
        _emit(sink, "stage_cache_hit", "normalize", "Cached normalized audio")
        return cache.normalized_path
    normalized = _run_stage(
        cache, "normalize", norm_sig,
        lambda: normalize_audio(vocals, cache.normalized_path), sink=sink, token=token,
    )
    cache.complete("normalize", norm_sig, path="normalized.wav")
    return normalized


def process_source(source: str, config: BuildConfig, event_sink: EventSink | None = None,
                   cancel_token: CancellationToken | None = None) -> ProcessSummary:
    _emit(event_sink, "pipeline_started", message=source)
    output = config.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache = PipelineCache(output, source, fresh=config.fresh)
    try:
        acquire_sig = cache.signature(source_identity(source))
        acquired = _acquire(source, cache, acquire_sig, event_sink, cancel_token)
        sep_sig = cache.signature({"parent": acquire_sig, "model": config.separator_model, "skip": config.skip_separation})
        norm_sig = cache.signature({"parent": sep_sig, "sample_rate": 44100})
        asr_sig = cache.signature({"parent": norm_sig, "model": config.asr_model, "language": config.language.lower()})

        transcript = cache.load_asr(asr_sig)
        normalized: Path | None = None
        if transcript:
            print(f"[cache] ASR hit: {cache.asr_path}", flush=True)
            _emit(event_sink, "stage_cache_hit", "asr", "Cached transcript")
        else:
            normalized = _ensure_normalized(acquired, config, cache, sep_sig, norm_sig, event_sink, cancel_token)
            def transcribe_action():
                kwargs = {"model_name": config.asr_model_path or config.asr_model, "language": config.language, "device": config.asr_device}
                if event_sink is not None or cancel_token is not None:
                    kwargs.update(event_sink=event_sink, cancel_token=cancel_token)
                return transcribe(normalized, **kwargs)
            transcript = _run_stage(cache, "asr", asr_sig, transcribe_action,
                                    sink=event_sink, token=cancel_token)
            cache.save_asr(asr_sig, transcript)

        _check(cancel_token)
        _emit(event_sink, "stage_started", "segment")
        language = _effective_language(config.language, transcript.language)
        candidates = build_clips(transcript.words, config.segment)
        accepted = [c for c in candidates if clip_is_acceptable(c, config.segment, config.min_confidence)]
        clip_sig = cache.signature({"parent": asr_sig, "segment": asdict(config.segment), "min_confidence": config.min_confidence})
        clips_cached = cache.stage_hit("clips", clip_sig) and clips_exist(output, acquired.source_id, len(accepted))
        if not clips_cached:
            if normalized is None:
                normalized = _ensure_normalized(acquired, config, cache, sep_sig, norm_sig, event_sink, cancel_token)
            audio, sample_rate = sf.read(normalized, dtype="float32")
            if getattr(audio, "ndim", 1) != 1:
                raise RuntimeError("normalized audio must be mono")
            remove_old_clips(output, acquired.source_id)
            for index, clip in enumerate(accepted, start=1):
                _check(cancel_token)
                write_clip(audio, sample_rate, clip, output / "clips" / f"{acquired.source_id}_{index:04d}.wav")
                _emit(event_sink, "stage_progress", "segment", f"Clip {index}/{len(accepted)}", index, len(accepted))
            cache.complete("clips", clip_sig, count=len(accepted))
        else:
            print("[cache] final clip audio hit", flush=True)
        _emit(event_sink, "stage_completed", "segment", f"{len(accepted)} clips")

        _check(cancel_token)
        _emit(event_sink, "stage_started", "export")
        records = [ManifestRecord(
            clip_id=f"{acquired.source_id}_{i:04d}", audio=(Path("clips") / f"{acquired.source_id}_{i:04d}.wav").as_posix(),
            source=acquired.original, speaker=config.speaker, language=language, start=clip.start, end=clip.end,
            text=clip.text, confidence=clip.confidence,
        ) for i, clip in enumerate(accepted, start=1)]
        replace_source_manifest(records, output / "manifest.jsonl", acquired.source_id)
        write_gpt_sovits_list(load_manifest(output / "manifest.jsonl"), output, output / "dataset.list")
        write_transcript(output / "transcripts" / f"{acquired.source_id}.json", acquired, transcript, candidates)
        cache.complete("export", cache.signature({"clips": clip_sig, "speaker": config.speaker, "language": language}),
                       accepted=len(records), rejected=len(candidates) - len(records))
        if not config.keep_temp:
            cache.compact()
        _emit(event_sink, "stage_completed", "export")
        summary = ProcessSummary(acquired.source_id, language, len(records), len(candidates) - len(records))
        _emit(event_sink, "pipeline_completed", message=f"Accepted {summary.accepted}, rejected {summary.rejected}")
        return summary
    except PipelineCancelled:
        _emit(event_sink, "pipeline_cancelled", message="Task cancelled; completed cache was preserved")
        raise
    except Exception as exc:
        _emit(event_sink, "pipeline_failed", message=str(exc))
        raise
