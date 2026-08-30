from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import requests

MIB = 1024 * 1024
PROBE_BYTES = 256 * 1024


def total_size(response, offset: int = 0) -> int | None:
    content_range = response.headers.get("Content-Range", "")
    match = re.search(r"/(\d+)$", content_range)
    if match:
        return int(match.group(1))
    length = response.headers.get("Content-Length")
    return offset + int(length) if length and length.isdigit() else None


def host_name(url: str) -> str:
    return urlparse(url).hostname or "unknown-cdn"


def new_session(base: requests.Session) -> requests.Session:
    session = requests.Session()
    session.headers.update(base.headers)
    session.cookies.update(base.cookies)
    session.proxies.update(base.proxies)
    return session


def probe_candidates(session, urls, referer: str, user_agent: str):
    print(f"[download] Probing {len(urls)} CDN candidate(s)...", flush=True)
    results = []
    for url in urls:
        headers = {
            "Referer": referer,
            "User-Agent": user_agent,
            "Range": f"bytes=0-{PROBE_BYTES - 1}",
        }
        try:
            started = time.monotonic()
            with session.get(url, headers=headers, stream=True, timeout=(3, 8)) as response:
                response.raise_for_status()
                if response.status_code != 206:
                    print(f"[download] {host_name(url)}: Range unsupported", flush=True)
                    continue
                total = total_size(response)
                received = sum(len(chunk) for chunk in response.iter_content(64 * 1024) if chunk)
            elapsed = max(time.monotonic() - started, 0.001)
            speed = received / MIB / elapsed
            if total:
                results.append((speed, url, total))
                print(f"[download] {host_name(url)}: {speed:.1f} MiB/s", flush=True)
        except (requests.RequestException, OSError) as exc:
            print(f"[download] {host_name(url)} probe failed: {exc}", flush=True)
    if not results:
        return list(urls), None, False
    results.sort(reverse=True, key=lambda item: item[0])
    return [item[1] for item in results], results[0][2], True
