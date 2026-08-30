from pathlib import Path


def test_windows_packaging_files_have_expected_shape():
    spec = Path('VoiceDatasetBuilder.spec').read_text(encoding='utf-8')
    script = Path('scripts/build_windows.ps1').read_text(encoding='utf-8')
    assert "name='VoiceDatasetBuilder'" in spec or 'name="VoiceDatasetBuilder"' in spec
    assert 'console=False' in spec
    assert 'COLLECT(' in spec
    assert 'voice_dataset_builder.py' in spec
    assert 'PyInstaller' in script
    assert 'VoiceDatasetBuilder.exe' in script
