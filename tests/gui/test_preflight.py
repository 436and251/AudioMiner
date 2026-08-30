from pathlib import Path
from tts_builder.config import BuildConfig
from tts_builder.gui.preflight import check_output_writable


def test_output_writable_creates_directory(tmp_path):
    target = tmp_path / 'new-output'
    check_output_writable(target)
    assert target.is_dir()
