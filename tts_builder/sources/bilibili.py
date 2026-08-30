from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

import requests

from ..models import AcquiredSource
from .common import source_id
from .download import download_fast
from .ytdlp import acquire_ytdlp

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}


def extract_bvid(value: str) -> str | None:
    match = re.search(r"\b(BV[0-9A-Za-z]{10})\b", value)
    return match.group(1) if match else None


def extract_playinfo(html: str) -> dict:
    match = re.search(r"window\.__playinfo__\s*=\s*", html)
    if not match:
        raise ValueError("embedded Bilibili playinfo was not found")
    decoder = json.JSONDecoder()
    payload, _ = decoder.raw_decode(html[match.end():])
    return payload


def select_best_audio_urls(playinfo: dict) -> list[str]:
    data = playinfo.get("data") or playinfo.get("result") or {}
    audio = (data.get("dash") or {}).get("audio") or []
    if not audio:
        raise ValueError("Bilibili response contains no DASH audio stream")
    best = max(audio, key=lambda item: int(item.get("bandwidth") or 0))
    base = best.get("baseUrl") or best.get("base_url") or best.get("url")
    backups = best.get("backupUrl") or best.get("backup_url") or []
    urls = [str(item) for item in [base, *backups] if item]
    urls = list(dict.fromkeys(urls))
    if not urls:
        raise ValueError("Bilibili DASH audio stream has no URL")
    return urls


def select_best_audio(playinfo: dict) -> str:
    return select_best_audio_urls(playinfo)[0]


def _page_title(html: str, fallback: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not match:
        return fallback
    title = re.sub(r"\s*_哔哩哔哩.*$", "", unescape(match.group(1))).strip()
    return title or fallback


def _api_playinfo(session: requests.Session, bvid: str) -> tuple[dict, str]:
    print("[bilibili] Fetching metadata...", flush=True)
    view = session.get(
        "https://api.bilibili.com/x/web-interface/view",
        params={"bvid": bvid}, timeout=(10, 30),
    )
    view.raise_for_status()
    view_data = view.json()
    if view_data.get("code") != 0:
        raise RuntimeError(f"Bilibili view API failed: {view_data.get('message')}")
    data = view_data["data"]
    cid = data.get("cid") or (data.get("pages") or [{}])[0].get("cid")
    if not cid:
        raise RuntimeError("Bilibili view API returned no cid")
    print(f"[bilibili] Metadata OK, cid={cid}", flush=True)
    print("[bilibili] Resolving DASH audio...", flush=True)
    play = session.get(
        "https://api.bilibili.com/x/player/playurl",
        params={"bvid": bvid, "cid": cid, "qn": 0, "fnval": 16, "fnver": 0, "fourk": 1},
        headers={"Referer": f"https://www.bilibili.com/video/{bvid}/"},
        timeout=(10, 30),
    )
    play.raise_for_status()
    payload = play.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"Bilibili playurl API failed: {payload.get('message')}")
    return payload, str(data.get("title") or bvid)



def _download_audio(
    session: requests.Session,
    urls: str | list[str],
    referer: str,
    target: Path,
    *,
    max_retries: int = 5,
    retry_delay: float = 1.0,
    event_sink=None, cancel_token=None,
) -> Path:
    candidates = [urls] if isinstance(urls, str) else urls
    return download_fast(
        session, candidates, referer, target, user_agent=UA,
        max_stalls=max_retries, retry_delay=retry_delay,
        event_sink=event_sink, cancel_token=cancel_token,
    )

def acquire_bilibili(url: str, temp_dir: Path, *, event_sink=None, cancel_token=None) -> AcquiredSource:
    errors: list[str] = []
    session = requests.Session()
    session.headers.update(HEADERS)
    bvid = extract_bvid(url)
    page_url = url
    print(f"[source] Bilibili: {bvid or url}", flush=True)
    try:
        if bvid:
            try:
                playinfo, label = _api_playinfo(session, bvid)
                audio_urls = select_best_audio_urls(playinfo)
                print("[bilibili] Audio stream resolved.", flush=True)
                page_url = f"https://www.bilibili.com/video/{bvid}/"
            except Exception as exc:
                errors.append(f"public API: {exc}")
                print(f"[bilibili] Public API failed: {exc}", flush=True)
                print("[bilibili] Trying embedded webpage playinfo...", flush=True)
                bvid = None

        if not bvid:
            page = session.get(url, timeout=(10, 30), allow_redirects=True)
            page.raise_for_status()
            page_url = page.url
            bvid = extract_bvid(page.url) or extract_bvid(page.text)
            if not bvid:
                raise RuntimeError("could not determine Bilibili BV id")
            label = _page_title(page.text, bvid)
            try:
                playinfo = extract_playinfo(page.text)
                audio_urls = select_best_audio_urls(playinfo)
            except Exception as exc:
                errors.append(f"embedded playinfo: {exc}")
                playinfo, label = _api_playinfo(session, bvid)
                audio_urls = select_best_audio_urls(playinfo)

        try:
            path = _download_audio(session, audio_urls, page_url, temp_dir / "bilibili_audio.m4a", event_sink=event_sink, cancel_token=cancel_token)
        except Exception as download_exc:
            if not bvid:
                raise
            print(f"[bilibili] CDN download failed: {download_exc}", flush=True)
            print("[bilibili] Refreshing signed audio URLs once...", flush=True)
            refreshed, _ = _api_playinfo(session, bvid)
            audio_urls = select_best_audio_urls(refreshed)
            path = _download_audio(session, audio_urls, page_url, temp_dir / "bilibili_audio.m4a", event_sink=event_sink, cancel_token=cancel_token)
        return AcquiredSource(str(path), label, source_id(label, url), url)
    except Exception as exc:
        errors.append(f"native Bilibili: {exc}")
        print(f"[bilibili] Native acquisition failed: {exc}", flush=True)
        print("[bilibili] Falling back to yt-dlp...", flush=True)
        try:
            return acquire_ytdlp(url, temp_dir, event_sink=event_sink, cancel_token=cancel_token)
        except Exception as fallback_exc:
            detail = "; ".join(errors)
            raise RuntimeError(
                f"Bilibili native and yt-dlp acquisition both failed. {detail}; "
                f"yt-dlp: {fallback_exc}"
            ) from fallback_exc
    finally:
        session.close()
