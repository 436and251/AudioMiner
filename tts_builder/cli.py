from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import BuildConfig
from .pipeline import process_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a multilingual TTS dataset from video URLs or local audio."
    )
    parser.add_argument("sources", nargs="+", help="YouTube/Bilibili URL or local audio file")
    parser.add_argument("--speaker", required=True, help="speaker name written to the dataset")
    parser.add_argument("--language", default="auto", help="audio language code, e.g. ja/zh/en, or auto")
    parser.add_argument("--output", default="dataset_out", help="dataset output directory")
    parser.add_argument("--asr-model", default="large-v3-turbo", help="faster-whisper model name")
    parser.add_argument("--asr-device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument(
        "--separator-device", choices=["auto", "cuda", "cpu"], default="auto"
    )
    parser.add_argument("--separator-model", default="htdemucs", help="Demucs model name")
    parser.add_argument(
        "--skip-separation", action="store_true",
        help="input is already clean vocals; skip Demucs",
    )
    parser.add_argument(
        "--keep-temp", action="store_true",
        help="keep separated/normalized full-length files after success for debugging",
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help="ignore reusable cache for this source and rebuild processing stages",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.5,
        help="minimum mean Whisper word confidence for a final clip",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = BuildConfig(
        output=Path(args.output),
        speaker=args.speaker,
        language=args.language,
        asr_model=args.asr_model,
        asr_device=args.asr_device,
        separator_model=args.separator_model,
        separator_device=args.separator_device,
        skip_separation=args.skip_separation,
        keep_temp=args.keep_temp,
        fresh=args.fresh,
        min_confidence=args.min_confidence,
    )
    failures = 0
    for index, source in enumerate(args.sources, start=1):
        print(f"\n[{index}/{len(args.sources)}] {source}")
        try:
            summary = process_source(source, config)
            print(
                f"  -> {summary.source_id}: language={summary.language}, "
                f"accepted={summary.accepted}, rejected={summary.rejected}"
            )
        except Exception as exc:
            failures += 1
            print(f"  ERROR: {exc}", file=sys.stderr)
    if failures:
        print(f"\nFinished with {failures} failed source(s).", file=sys.stderr)
        return 1
    print(f"\nDataset ready: {config.output.resolve()}")
    return 0
