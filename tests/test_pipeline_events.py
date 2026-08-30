from pathlib import Path

from tts_builder.config import BuildConfig
from tts_builder.events import CancellationToken, PipelineEvent
from tts_builder.models import AcquiredSource, TranscriptResult, WordStamp
from tts_builder.pipeline import process_source


def test_pipeline_emits_stage_events(tmp_path, monkeypatch):
    monkeypatch.setattr('tts_builder.pipeline.acquire_source', lambda s, d, **kw: AcquiredSource('/tmp/a.wav', 'a', 'src1', s))
    monkeypatch.setattr('tts_builder.pipeline.separate_vocals', lambda *a, **kw: Path('/tmp/vocals.flac'))
    monkeypatch.setattr('tts_builder.pipeline.normalize_audio', lambda i, o, **kw: o)
    monkeypatch.setattr('tts_builder.pipeline.transcribe', lambda *a, **kw: TranscriptResult('ja', 1.0, [], [WordStamp(0,4,' hello',0.99)]))
    monkeypatch.setattr('tts_builder.pipeline.sf.read', lambda *a, **kw: ([0.0] * 200000, 44100))
    monkeypatch.setattr('tts_builder.pipeline.write_clip', lambda *a, **kw: None)
    monkeypatch.setattr('tts_builder.pipeline.clips_exist', lambda *a, **kw: False)
    monkeypatch.setattr('tts_builder.pipeline.remove_old_clips', lambda *a, **kw: None)
    monkeypatch.setattr('tts_builder.pipeline.replace_source_manifest', lambda *a, **kw: None)
    monkeypatch.setattr('tts_builder.pipeline.write_gpt_sovits_list', lambda *a, **kw: None)
    monkeypatch.setattr('tts_builder.pipeline.load_manifest', lambda *a, **kw: [])
    monkeypatch.setattr('tts_builder.pipeline.write_transcript', lambda *a, **kw: None)
    events = []
    config = BuildConfig(output=tmp_path, speaker='s', language='ja', skip_separation=True)
    process_source('dummy', config, event_sink=events.append)
    kinds = [(e.kind, e.stage) for e in events]
    assert ('pipeline_started', None) in kinds
    for stage in ('source','separate','normalize','asr','segment','export'):
        assert any(e.stage == stage for e in events)
    assert events[-1].kind == 'pipeline_completed'
