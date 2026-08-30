# Media Sources Refactor Design

## Goal

Replace the single yt-dlp URL acquisition path with three focused sources while preserving the existing TTS pipeline:

- `LocalFileSource` for local files.
- `BilibiliSource` for public Bilibili videos.
- `YtDlpSource` for YouTube and generic supported sites, and as Bilibili fallback.

## Constraints

- Python 3.12.
- Keep the CLI entry simple and backwards compatible.
- Default ASR stays `large-v3-turbo`.
- Keep production files focused and under roughly 200 lines.
- Do not add a web service or FastAPI layer.
- Do not require browser cookies for normal public Bilibili videos.
- Preserve Demucs, faster-whisper, segmentation, manifest, and GPT-SoVITS export behavior.

## Architecture

`acquire_source()` delegates to a source router. Local paths go directly to `LocalFileSource`. Bilibili URLs go to `BilibiliSource`, which first fetches the page and extracts `window.__playinfo__`; if unavailable it queries Bilibili's public metadata and legacy playurl endpoints for DASH audio. If native acquisition fails, the source falls back to `YtDlpSource`. Other HTTP URLs go directly to `YtDlpSource`.

The source layer always returns the existing `AcquiredSource`, so the downstream pipeline is unchanged.

## Bilibili Data Flow

1. Normalize/extract a BV id from the URL.
2. Request the video page with browser-like headers.
3. Parse title and embedded `window.__playinfo__` JSON.
4. Choose the highest-bandwidth entry from `dash.audio`.
5. If embedded playinfo is absent, call `/x/web-interface/view` to get title/cid.
6. Call `/x/player/playurl` requesting DASH audio.
7. Stream the selected audio URL to a temporary `.m4a` file with Bilibili Referer.
8. On any native failure, log the reason and fall back to yt-dlp.

## Error Handling

- Native Bilibili failures are accumulated and included in the final error if yt-dlp also fails.
- HTTP requests use finite connect/read timeouts.
- Downloaded streams must be non-empty.
- Bilibili parsing helpers are pure functions and unit-tested without network access.

## Testing

- URL platform detection and routing.
- BVID extraction.
- Embedded playinfo extraction.
- Best audio selection by bandwidth.
- Existing media, CLI, pipeline, dataset, separator, and segmenter tests remain green.
