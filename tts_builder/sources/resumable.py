from __future__ import annotations

import time
from pathlib import Path

import requests

from ..events import PipelineEvent, emit

from .http_download import MIB, total_size

NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def _show(done: int, total: int, transferred: int, started: float) -> None:
    elapsed = max(time.monotonic() - started, 0.001)
    speed = transferred / MIB / elapsed
    percent = min(done / total * 100, 100.0)
    print(
        f"\r[download] {done/MIB:.1f} / {total/MIB:.1f} MiB  "
        f"{percent:5.1f}%  {speed:.1f} MiB/s",
        end="", flush=True,
    )


def download_resumable(session: requests.Session, url: str, referer: str, target: Path,
                       *, user_agent: str, max_retries: int = 5,
                       retry_delay: float = 1.0, event_sink=None, cancel_token=None) -> Path:
    part = target.with_suffix(target.suffix + ".part")
    stalls = 0
    transferred = 0
    started = time.monotonic()
    while True:
        if cancel_token:
            cancel_token.raise_if_cancelled()
        offset = part.stat().st_size if part.exists() else 0
        headers = {"Referer": referer, "User-Agent": user_agent}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            with session.get(url, headers=headers, stream=True, timeout=(10, 120)) as response:
                response.raise_for_status()
                if offset and response.status_code != 206:
                    offset = 0
                mode = "ab" if offset and response.status_code == 206 else "wb"
                total = total_size(response, offset)
                done = offset
                with part.open(mode) as handle:
                    for chunk in response.iter_content(MIB):
                        if cancel_token:
                            cancel_token.raise_if_cancelled()
                        if not chunk:
                            continue
                        handle.write(chunk)
                        done += len(chunk)
                        transferred += len(chunk)
                        if total:
                            _show(done, total, transferred, started)
                            emit(event_sink, PipelineEvent("stage_progress", "source", "Downloading media", done, total))
                if total and done < total:
                    raise requests.exceptions.ChunkedEncodingError("incomplete download")
            print(flush=True)
            part.replace(target)
            return target
        except requests.exceptions.HTTPError:
            raise
        except NETWORK_ERRORS as exc:
            current = part.stat().st_size if part.exists() else 0
            stalls = 0 if current > offset else stalls + 1
            if stalls >= max_retries:
                raise RuntimeError(
                    f"audio download stalled for {max_retries} consecutive attempts: {exc}"
                ) from exc
            print(f"\n[download] Interrupted; resuming from {current/MIB:.1f} MiB...", flush=True)
            if retry_delay:
                time.sleep(retry_delay)
