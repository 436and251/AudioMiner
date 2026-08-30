import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
pytest.importorskip('PySide6')

from tts_builder.gui.app import create_application
from tts_builder.gui.main_window import MainWindow
from tts_builder.gui.settings import AppSettings


def test_main_window_enables_start_only_with_source_and_speaker(tmp_path):
    app = create_application([])
    window = MainWindow(AppSettings(first_run_completed=True, model_root=tmp_path/'models', output_root=tmp_path/'out'))
    assert not window.start.isEnabled()
    window.source.set_value(str(tmp_path/'input.wav'))
    window.speaker.setText('suis')
    app.processEvents()
    assert window.start.isEnabled()
    window.close()
