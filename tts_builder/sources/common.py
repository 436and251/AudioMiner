from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def source_id(label: str, stable_key: str) -> str:
    stem = Path(label).stem
    ascii_text = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_text).strip("_-").lower()
    slug = slug or "source"
    digest = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()[:8]
    return f"{slug[:48]}_{digest}"[:64]
