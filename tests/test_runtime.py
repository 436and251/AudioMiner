from pathlib import Path
import tts_builder.runtime as runtime


def test_resolve_binary_prefers_application_bin(tmp_path, monkeypatch):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    name = 'ffmpeg.exe' if runtime.os.name == 'nt' else 'ffmpeg'
    target = bin_dir / name
    target.write_text('x')
    monkeypatch.setattr(runtime, 'application_dir', lambda: tmp_path)
    monkeypatch.setattr(runtime.shutil, 'which', lambda name: '/path/fallback')
    assert runtime.resolve_binary('ffmpeg') == str(target)
