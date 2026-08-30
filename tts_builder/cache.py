from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path

from .models import AcquiredSource, TranscriptResult, TranscriptSegment, WordStamp
from .sources.common import is_url


def _digest(payload) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def source_identity(value: str) -> dict:
    match = re.search(r"\b(BV[0-9A-Za-z]{10})\b", value)
    if match:
        return {"kind": "bilibili", "bvid": match.group(1)}
    if is_url(value):
        return {"kind": "url", "url": value}
    path = Path(value).expanduser().resolve()
    stat = path.stat() if path.exists() else None
    return {
        "kind": "local",
        "path": str(path),
        "size": stat.st_size if stat else None,
        "mtime_ns": stat.st_mtime_ns if stat else None,
    }


def cache_key(value: str) -> str:
    identity = source_identity(value)
    if identity["kind"] == "bilibili":
        return f"bilibili_{identity['bvid']}"
    stem = Path(value).stem if identity["kind"] == "local" else "source"
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "source"
    return f"{safe[:32]}_{_digest(identity)[:10]}"


class PipelineCache:
    def __init__(self, output: Path, source: str, fresh: bool = False):
        self.root = output / ".cache" / cache_key(source)
        if fresh:
            shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "state.json"
        self.state = self._load_state(source)

    @property
    def source_dir(self) -> Path:
        path = self.root / "source"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def normalized_path(self) -> Path:
        return self.root / "normalized.wav"

    @property
    def asr_path(self) -> Path:
        return self.root / "asr.json"

    def signature(self, payload) -> str:
        return _digest(payload)

    def stage_hit(self, name: str, signature: str, path: Path | None = None) -> bool:
        stage = self.state.get("stages", {}).get(name, {})
        if stage.get("status") != "completed" or stage.get("signature") != signature:
            return False
        return path is None or path.exists()

    def stage_data(self, name: str) -> dict:
        return self.state.get("stages", {}).get(name, {})

    def begin(self, name: str, signature: str) -> None:
        self._set_stage(name, {"status": "running", "signature": signature})

    def complete(self, name: str, signature: str, **data) -> None:
        self._set_stage(name, {"status": "completed", "signature": signature, **data})

    def fail(self, name: str, signature: str, error: Exception) -> None:
        self._set_stage(
            name,
            {"status": "failed", "signature": signature, "error": str(error)},
        )

    def save_acquired(self, signature: str, acquired: AcquiredSource) -> None:
        self.complete(
            "acquire",
            signature,
            path=self._stored_path(Path(acquired.path)),
            label=acquired.label,
            source_id=acquired.source_id,
            original=acquired.original,
        )

    def load_acquired(self, signature: str) -> AcquiredSource | None:
        stage = self.stage_data("acquire")
        if stage.get("status") != "completed" or stage.get("signature") != signature:
            return None
        path = self._resolved_path(stage.get("path", ""))
        if not path.exists():
            return None
        return AcquiredSource(
            str(path), stage["label"], stage["source_id"], stage["original"]
        )

    def save_asr(self, signature: str, transcript: TranscriptResult) -> None:
        payload = {
            "language": transcript.language,
            "language_probability": transcript.language_probability,
            "segments": [asdict(item) for item in transcript.segments],
            "words": [asdict(item) for item in transcript.words],
        }
        self._atomic_json(self.asr_path, payload)
        self.complete("asr", signature, path="asr.json")

    def load_asr(self, signature: str) -> TranscriptResult | None:
        if not self.stage_hit("asr", signature, self.asr_path):
            return None
        data = json.loads(self.asr_path.read_text(encoding="utf-8"))
        return TranscriptResult(
            language=data["language"],
            language_probability=float(data["language_probability"]),
            segments=[TranscriptSegment(**item) for item in data["segments"]],
            words=[WordStamp(**item) for item in data["words"]],
        )

    def compact(self) -> None:
        shutil.rmtree(self.root / "separated", ignore_errors=True)
        self.normalized_path.unlink(missing_ok=True)

    def _load_state(self, source: str) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"version": 1, "source": source, "stages": {}}

    def _set_stage(self, name: str, data: dict) -> None:
        self.state.setdefault("stages", {})[name] = data
        self._atomic_json(self.state_path, self.state)

    def _stored_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(path.resolve())

    def _resolved_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    @staticmethod
    def _atomic_json(path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
