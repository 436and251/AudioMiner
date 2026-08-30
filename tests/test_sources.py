from tts_builder.sources.bilibili import (
    extract_bvid,
    extract_playinfo,
    select_best_audio,
)
from tts_builder.sources.router import is_bilibili_url


def test_bilibili_url_detection_accepts_video_and_short_links():
    assert is_bilibili_url("https://www.bilibili.com/video/BV1hCNuzkEQi/")
    assert is_bilibili_url("https://b23.tv/abc123")
    assert not is_bilibili_url("https://www.youtube.com/watch?v=abc")


def test_extract_bvid_from_standard_url():
    assert extract_bvid("https://www.bilibili.com/video/BV1hCNuzkEQi/") == "BV1hCNuzkEQi"


def test_extract_playinfo_reads_embedded_json():
    html = '''
    <html><script>
    window.__playinfo__={"code":0,"data":{"dash":{"audio":[{"bandwidth":64000,"baseUrl":"https://a/low"},{"bandwidth":192000,"base_url":"https://a/high"}]}}};
    </script></html>
    '''
    playinfo = extract_playinfo(html)
    assert playinfo["code"] == 0
    assert playinfo["data"]["dash"]["audio"][1]["bandwidth"] == 192000


def test_select_best_audio_prefers_highest_bandwidth_and_url_aliases():
    playinfo = {
        "data": {
            "dash": {
                "audio": [
                    {"bandwidth": 128000, "baseUrl": "https://a/128"},
                    {"bandwidth": 192000, "base_url": "https://a/192"},
                ]
            }
        }
    }
    assert select_best_audio(playinfo) == "https://a/192"


def test_extract_playinfo_allows_whitespace_around_assignment():
    html = '<script>window.__playinfo__ = {"code":0,"data":{"dash":{"audio":[]}}};</script>'
    assert extract_playinfo(html)["code"] == 0


def test_router_sends_bilibili_to_native_backend(monkeypatch, tmp_path):
    from tts_builder.models import AcquiredSource
    from tts_builder.sources import router

    expected = AcquiredSource("a.m4a", "title", "id", "source")
    monkeypatch.setattr(router, "acquire_bilibili", lambda url, temp: expected)
    monkeypatch.setattr(router, "acquire_ytdlp", lambda url, temp: (_ for _ in ()).throw(AssertionError()))
    assert router.acquire_source("https://www.bilibili.com/video/BV1hCNuzkEQi/", tmp_path) == expected


def test_router_sends_generic_url_to_ytdlp(monkeypatch, tmp_path):
    from tts_builder.models import AcquiredSource
    from tts_builder.sources import router

    expected = AcquiredSource("a.webm", "title", "id", "source")
    monkeypatch.setattr(router, "acquire_ytdlp", lambda url, temp: expected)
    assert router.acquire_source("https://www.youtube.com/watch?v=abc", tmp_path) == expected


class _FakeResponse:
    def __init__(self, chunks, *, status_code=200, headers=None, fail_after=None):
        self._chunks = chunks
        self.status_code = status_code
        self.headers = headers or {}
        self._fail_after = fail_after

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        import requests
        for index, chunk in enumerate(self._chunks):
            if self._fail_after is not None and index == self._fail_after:
                raise requests.exceptions.ChunkedEncodingError("connection interrupted")
            yield chunk


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_bilibili_audio_download_resumes_partial_file(tmp_path):
    from tts_builder.sources.resumable import download_resumable

    first = _FakeResponse(
        [b"abc", b"def"],
        headers={"Content-Length": "9"},
        fail_after=1,
    )
    second = _FakeResponse(
        [b"def", b"ghi"],
        status_code=206,
        headers={"Content-Length": "6", "Content-Range": "bytes 3-8/9"},
    )
    session = _FakeSession([first, second])
    target = tmp_path / "audio.m4a"

    result = download_resumable(
        session, "https://audio.example/file", "https://www.bilibili.com/", target,
        user_agent="ua", retry_delay=0,
    )

    assert result == target
    assert target.read_bytes() == b"abcdefghi"
    assert not target.with_suffix(target.suffix + ".part").exists()
    assert "Range" not in session.calls[0][1]["headers"]
    assert session.calls[1][1]["headers"]["Range"] == "bytes=3-"


def test_bilibili_audio_download_restarts_when_server_ignores_range(tmp_path):
    from tts_builder.sources.resumable import download_resumable

    first = _FakeResponse(
        [b"abc", b"def"],
        headers={"Content-Length": "6"},
        fail_after=1,
    )
    second = _FakeResponse(
        [b"ABC", b"DEF"],
        status_code=200,
        headers={"Content-Length": "6"},
    )
    session = _FakeSession([first, second])
    target = tmp_path / "audio.m4a"

    download_resumable(
        session, "https://audio.example/file", "https://www.bilibili.com/", target,
        user_agent="ua", retry_delay=0,
    )

    assert target.read_bytes() == b"ABCDEF"
    assert session.calls[1][1]["headers"]["Range"] == "bytes=3-"


def test_bilibili_audio_download_prints_progress(tmp_path, capsys):
    from tts_builder.sources.resumable import download_resumable

    response = _FakeResponse([b"abc", b"def"], headers={"Content-Length": "6"})
    session = _FakeSession([response])

    download_resumable(
        session, "https://audio.example/file", "https://www.bilibili.com/",
        tmp_path / "audio.m4a", user_agent="ua", retry_delay=0,
    )

    output = capsys.readouterr().out
    assert "[download]" in output
    assert "100.0%" in output


def test_select_best_audio_urls_includes_base_and_backups_without_duplicates():
    from tts_builder.sources.bilibili import select_best_audio_urls

    playinfo = {
        "data": {
            "dash": {
                "audio": [
                    {
                        "bandwidth": 192000,
                        "baseUrl": "https://cdn-a/audio",
                        "backupUrl": [
                            "https://cdn-b/audio",
                            "https://cdn-a/audio",
                            "https://cdn-c/audio",
                        ],
                    },
                    {"bandwidth": 128000, "baseUrl": "https://low/audio"},
                ]
            }
        }
    }

    assert select_best_audio_urls(playinfo) == [
        "https://cdn-a/audio",
        "https://cdn-b/audio",
        "https://cdn-c/audio",
    ]


def test_segmented_download_keeps_progress_and_switches_cdn(monkeypatch, tmp_path):
    from tts_builder.sources import download

    payload = b"abcdefghijkl"
    calls = []
    attempts = {("https://cdn-a/audio", "bytes=0-5"): 0}

    class Response(_FakeResponse):
        pass

    class RangeSession:
        headers = {}
        cookies = {}
        proxies = {}

        def close(self):
            pass

        def get(self, url, **kwargs):
            byte_range = kwargs["headers"]["Range"]
            calls.append((url, byte_range))
            start_end = byte_range.removeprefix("bytes=").split("-")
            start, end = map(int, start_end)
            body = payload[start:end + 1]
            key = (url, byte_range)
            if key == ("https://cdn-a/audio", "bytes=0-5") and attempts[key] == 0:
                attempts[key] += 1
                return Response([body[:3], body[3:]], status_code=206, fail_after=1)
            return Response([body], status_code=206)

    monkeypatch.setattr(
        download,
        "_probe_candidates",
        lambda *args, **kwargs: (["https://cdn-a/audio", "https://cdn-b/audio"], len(payload), True),
    )
    monkeypatch.setattr(download, "_new_session", lambda base: RangeSession())

    target = tmp_path / "audio.m4a"
    result = download.download_fast(
        _FakeSession([]),
        ["https://cdn-a/audio", "https://cdn-b/audio"],
        "https://www.bilibili.com/",
        target,
        user_agent="ua",
        segment_size=6,
        workers=1,
        max_stalls=1,
        retry_delay=0,
    )

    assert result == target
    assert target.read_bytes() == payload
    assert ("https://cdn-b/audio", "bytes=3-5") in calls


def test_segmented_download_does_not_consume_stall_budget_when_bytes_advance(monkeypatch, tmp_path):
    from tts_builder.sources import download

    payload = b"abcdefgh"
    responses = [
        _FakeResponse([b"ab", b"cd"], status_code=206, fail_after=1),
        _FakeResponse([b"cd", b"ef"], status_code=206, fail_after=1),
        _FakeResponse([b"efgh"], status_code=206),
    ]

    class RangeSession:
        headers = {}
        cookies = {}
        proxies = {}

        def close(self):
            pass

        def get(self, url, **kwargs):
            return responses.pop(0)

    monkeypatch.setattr(
        download,
        "_probe_candidates",
        lambda *args, **kwargs: (["https://cdn-a/audio"], len(payload), True),
    )
    monkeypatch.setattr(download, "_new_session", lambda base: RangeSession())

    target = tmp_path / "audio.m4a"
    download.download_fast(
        _FakeSession([]), ["https://cdn-a/audio"], "https://www.bilibili.com/", target,
        user_agent="ua", segment_size=len(payload), workers=1, max_stalls=1, retry_delay=0,
    )

    assert target.read_bytes() == payload
