from __future__ import annotations

from pathlib import Path

from .events import CancellationToken, EventSink, PipelineEvent, emit


def run_demucs(input_path: Path, output_root: Path, model: str, device: str,
               segment_seconds: float, event_sink: EventSink | None = None,
               cancel_token: CancellationToken | None = None) -> None:
    if cancel_token:
        cancel_token.raise_if_cancelled()
    try:
        from demucs.separate import main as demucs_main
    except ImportError as exc:
        raise RuntimeError("Demucs is required: pip install demucs") from exc
    args = [
        "-n", model, "--two-stems=vocals", "--other-method", "none",
        "--flac", "--segment", str(int(segment_seconds)), "-o", str(output_root),
    ]
    if device != "auto":
        args.extend(["-d", device])
    args.append(str(input_path))
    emit(event_sink, PipelineEvent("log", "separate", f"Demucs model: {model}"))
    demucs_main(args)
    if cancel_token:
        cancel_token.raise_if_cancelled()
