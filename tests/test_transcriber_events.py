import sys
from types import SimpleNamespace
from pathlib import Path

from tts_builder.events import CancellationToken
from tts_builder.transcriber import transcribe


def test_transcriber_emits_segment_progress(monkeypatch, tmp_path):
    class Model:
        def __init__(self, *a, **k): pass
        def transcribe(self, *a, **k):
            word = SimpleNamespace(start=0.0, end=2.0, word=' hi', probability=0.9)
            seg = SimpleNamespace(start=0.0, end=2.0, text='hi', words=[word])
            return iter([seg]), SimpleNamespace(language='en', language_probability=0.99)
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=Model))
    monkeypatch.setattr('tts_builder.transcriber._resolve_device', lambda d: ('cpu','int8'))
    monkeypatch.setattr('tts_builder.transcriber._audio_duration', lambda p: 10.0)
    events=[]
    result = transcribe(tmp_path/'a.wav', event_sink=events.append)
    progress=[e for e in events if e.kind=='stage_progress']
    assert progress[-1].current == 2.0
    assert progress[-1].total == 10.0
    assert result.language == 'en'
