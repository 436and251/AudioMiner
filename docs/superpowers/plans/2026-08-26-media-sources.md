# Media Sources Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add native public Bilibili audio acquisition plus clean local/generic source routing without changing the downstream TTS pipeline.

**Architecture:** Introduce `tts_builder/sources/` with focused local, Bilibili, yt-dlp, and router modules. Keep `tts_builder.media` as the stable facade for acquisition and normalization.

**Tech Stack:** Python 3.12, requests, yt-dlp, FFmpeg, pytest.

**Spec:** `docs/superpowers/specs/2026-08-26-media-sources-design.md`

## Global Constraints

- Python 3.12.
- Default ASR stays `large-v3-turbo`.
- Keep production files focused and under roughly 200 lines.
- Public Bilibili acquisition must not require browser cookies.
- Preserve the existing `AcquiredSource` interface.

---

### Task 1: Source routing and parsing contracts

**Files:**
- Create: `tts_builder/sources/common.py`
- Create: `tts_builder/sources/router.py`
- Create: `tests/test_sources.py`

**Interfaces:**
- Produces: `is_url(value)`, `source_id(label, stable_key)`, `is_bilibili_url(url)`, `acquire_source(value, temp_dir)`.

- [ ] Write tests for Bilibili detection, BVID extraction, playinfo parsing, and best-audio selection.
- [ ] Run the source tests and verify they fail because the source modules do not exist.
- [ ] Implement the smallest source modules required by the tests.
- [ ] Run the source tests until green.

### Task 2: Native Bilibili acquisition and yt-dlp fallback

**Files:**
- Create: `tts_builder/sources/bilibili.py`
- Create: `tts_builder/sources/ytdlp.py`
- Create: `tts_builder/sources/local.py`
- Modify: `tts_builder/media.py`

**Interfaces:**
- Consumes: existing `AcquiredSource`.
- Produces: an acquired local audio path for every supported source.

- [ ] Add tests that exercise routing boundaries without live network access.
- [ ] Verify the tests fail before implementation.
- [ ] Implement page playinfo, public playurl, stream download, and yt-dlp fallback.
- [ ] Run source and media tests until green.

### Task 3: Documentation and regression verification

**Files:**
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] Document the new source strategy and Bilibili fallback behavior.
- [ ] Run the full pytest suite.
- [ ] Run `python -m compileall` on the package.
- [ ] Verify production Python file sizes remain within the project readability constraint.
- [ ] Build a clean ZIP excluding caches.
