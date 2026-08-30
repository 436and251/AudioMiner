from __future__ import annotations

from pathlib import Path

from ..runtime import resolve_binary


def check_output_writable(path: Path) -> None:
    path = Path(path).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".vdb_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
    finally:
        probe.unlink(missing_ok=True)


def check_runtime(output: Path) -> None:
    check_output_writable(output)
    resolve_binary("ffmpeg")
