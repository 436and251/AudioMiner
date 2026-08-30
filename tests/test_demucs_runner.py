import sys
from types import ModuleType
from pathlib import Path

from tts_builder.demucs_runner import run_demucs


def test_run_demucs_calls_importable_main(monkeypatch, tmp_path):
    calls = []
    demucs = ModuleType('demucs')
    separate = ModuleType('demucs.separate')
    separate.main = lambda args: calls.append(args)
    monkeypatch.setitem(sys.modules, 'demucs', demucs)
    monkeypatch.setitem(sys.modules, 'demucs.separate', separate)
    run_demucs(Path('input.wav'), tmp_path, 'htdemucs', 'cpu', 7)
    assert calls
    assert '--two-stems=vocals' in calls[0]
    assert '-d' in calls[0]
    assert 'cpu' in calls[0]
