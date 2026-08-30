from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def application_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resolve_binary(name: str) -> str:
    suffix = ".exe" if os.name == "nt" and not name.lower().endswith(".exe") else ""
    candidate = application_dir() / "bin" / f"{name}{suffix}"
    if candidate.is_file():
        return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    raise RuntimeError(f"{name} was not found. Install it or place it in the application bin directory.")
