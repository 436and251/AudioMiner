from pathlib import Path

from tts_builder.separator import build_demucs_command


def test_demucs_command_writes_only_lossless_vocal_stem():
    command = build_demucs_command(
        Path("input.m4a"), Path("out"), model="htdemucs", device="auto", segment_seconds=7
    )
    assert "--two-stems=vocals" in command
    assert "--other-method" in command
    assert command[command.index("--other-method") + 1] == "none"
    assert "--flac" in command
    assert "-d" not in command
