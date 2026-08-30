from __future__ import annotations

import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import requests

from ..events import PipelineEvent, emit

from .http_download import MIB, host_name as _host, new_session as _new_session
from .http_download import probe_candidates as _probe_candidates
from .resumable import download_resumable


class _Progress:
    def __init__(self, done: int, total: int, event_sink=None):
        self.done = done
        self.total = total
        self.new_bytes = 0
        self.started = time.monotonic()
        self.lock = Lock()
        self.event_sink = event_sink

    def add(self, size: int) -> None:
        with self.lock:
            self.done += size
            self.new_bytes += size
            elapsed = max(time.monotonic() - self.started, 0.001)
            speed = self.new_bytes / MIB / elapsed
            percent = min(self.done / self.total * 100, 100.0)
            print(
                f"\r[download] {self.done/MIB:.1f} / {self.total/MIB:.1f} MiB  "
                f"{percent:5.1f}%  {speed:.1f} MiB/s", end="", flush=True,
            )
            emit(self.event_sink, PipelineEvent(
                "stage_progress", "source", f"{percent:.1f}% · {speed:.1f} MiB/s",
                self.done, self.total, {"speed_mib_s": speed},
            ))


def _segment_file(parts_dir: Path, index: int) -> Path:
    return parts_dir / f"segment_{index:04d}.part"


def _download_segment(base_session, urls, referer, user_agent, parts_dir, index,
                      start, end, progress, max_stalls, retry_delay, cancel_token=None):
    path = _segment_file(parts_dir, index)
    expected = end - start + 1
    current = min(path.stat().st_size if path.exists() else 0, expected)
    if path.exists() and path.stat().st_size != current:
        with path.open("r+b") as handle:
            handle.truncate(current)
    stalls = 0
    attempt = 0
    session = _new_session(base_session)
    try:
        while current < expected:
            if cancel_token:
                cancel_token.raise_if_cancelled()
            url = urls[(index + attempt) % len(urls)]
            before = current
            headers = {
                "Referer": referer,
                "User-Agent": user_agent,
                "Range": f"bytes={start + current}-{end}",
            }
            try:
                with session.get(url, headers=headers, stream=True, timeout=(10, 45)) as response:
                    response.raise_for_status()
                    if response.status_code != 206:
                        raise RuntimeError("CDN ignored Range request")
                    with path.open("ab") as handle:
                        for chunk in response.iter_content(MIB):
                            if cancel_token:
                                cancel_token.raise_if_cancelled()
                            if not chunk:
                                continue
                            chunk = chunk[: expected - current]
                            handle.write(chunk)
                            current += len(chunk)
                            progress.add(len(chunk))
                            if current >= expected:
                                break
                if current == before:
                    raise requests.exceptions.ConnectionError("range returned no data")
                stalls = 0
            except (requests.RequestException, RuntimeError, OSError) as exc:
                current = min(path.stat().st_size if path.exists() else 0, expected)
                stalls = 0 if current > before else stalls + 1
                attempt += 1
                print(
                    f"\n[download] Segment {index + 1} interrupted on {_host(url)}: {exc}",
                    flush=True,
                )
                if stalls >= max_stalls:
                    raise RuntimeError(
                        f"segment {index + 1} made no progress for {max_stalls} attempts"
                    ) from exc
                if retry_delay:
                    time.sleep(retry_delay)
    finally:
        session.close()
    return path


def _merge_segments(parts_dir: Path, segments, target: Path, total: int) -> Path:
    part = target.with_suffix(target.suffix + ".part")
    with part.open("wb") as output:
        for index, (start, end) in enumerate(segments):
            path = _segment_file(parts_dir, index)
            expected = end - start + 1
            if not path.is_file() or path.stat().st_size != expected:
                raise RuntimeError(f"segment {index + 1} is incomplete")
            with path.open("rb") as source:
                shutil.copyfileobj(source, output)
    if part.stat().st_size != total:
        raise RuntimeError(f"merged audio size mismatch: {part.stat().st_size} != {total}")
    part.replace(target)
    shutil.rmtree(parts_dir, ignore_errors=True)
    return target


def download_fast(session: requests.Session, urls, referer: str, target: Path, *,
                  user_agent: str, segment_size: int = 8 * MIB, workers: int = 4,
                  max_stalls: int = 5, retry_delay: float = 0.5,
                  event_sink=None, cancel_token=None) -> Path:
    urls = list(dict.fromkeys(urls))
    ranked, total, ranged = _probe_candidates(session, urls, referer, user_agent)
    if not ranged or not total:
        print("[download] Ranged CDN download unavailable; using resumable mode.", flush=True)
        return download_resumable(
            session, urls[0], referer, target, user_agent=user_agent,
            max_retries=max_stalls, retry_delay=retry_delay,
            event_sink=event_sink, cancel_token=cancel_token,
        )

    parts_dir = target.with_suffix(target.suffix + ".parts")
    parts_dir.mkdir(parents=True, exist_ok=True)
    segments = [(start, min(start + segment_size, total) - 1) for start in range(0, total, segment_size)]
    initial = sum(
        min(_segment_file(parts_dir, i).stat().st_size, end - start + 1)
        if _segment_file(parts_dir, i).exists() else 0
        for i, (start, end) in enumerate(segments)
    )
    progress = _Progress(initial, total, event_sink)
    count = min(max(1, workers), len(segments))
    print(
        f"[download] {total/MIB:.1f} MiB, {len(segments)} segment(s), "
        f"{count} worker(s), {len(ranked)} CDN(s).",
        flush=True,
    )

    with ThreadPoolExecutor(max_workers=count) as pool:
        futures = []
        for index, (start, end) in enumerate(segments):
            path = _segment_file(parts_dir, index)
            if path.exists() and path.stat().st_size == end - start + 1:
                continue
            futures.append(pool.submit(
                _download_segment, session, ranked, referer, user_agent, parts_dir,
                index, start, end, progress, max_stalls, retry_delay, cancel_token,
            ))
        for future in as_completed(futures):
            future.result()

    print(flush=True)
    result = _merge_segments(parts_dir, segments, target, total)
    print(f"[download] Completed: {target.stat().st_size/MIB:.1f} MiB", flush=True)
    return result
