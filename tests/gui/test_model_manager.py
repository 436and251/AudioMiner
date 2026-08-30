from pathlib import Path
from tts_builder.gui.model_manager import asr_repo_id, estimated_asr_bytes, friendly_download_error


def test_large_turbo_repo_mapping():
    assert asr_repo_id('large-v3-turbo') == 'mobiuslabsgmbh/faster-whisper-large-v3-turbo'
    assert estimated_asr_bytes('large-v3-turbo') > 1_000_000_000


def test_custom_repo_id_passes_through():
    assert asr_repo_id('org/repo') == 'org/repo'


def test_friendly_network_error_is_actionable():
    title, message = friendly_download_error(RuntimeError('HTTPSConnectionPool Read timed out'))
    assert 'Network' in title
    assert 'preserved' in message
