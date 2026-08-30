from pathlib import Path
from tts_builder.gui.settings import AppSettings, apply_model_environment


def test_settings_round_trip(tmp_path: Path):
    path = tmp_path / 'config.json'
    settings = AppSettings(
        first_run_completed=True,
        model_root=tmp_path / 'models',
        output_root=tmp_path / 'datasets',
        preferred_asr_model='large-v3-turbo',
    )
    settings.save(path)
    loaded = AppSettings.load(path)
    assert loaded == settings


def test_apply_model_environment_sets_separate_caches(tmp_path: Path, monkeypatch):
    root = tmp_path / 'models'
    monkeypatch.delenv('HF_HOME', raising=False)
    monkeypatch.delenv('TORCH_HOME', raising=False)
    apply_model_environment(root)
    import os
    assert os.environ['HF_HOME'] == str(root / 'huggingface')
    assert os.environ['TORCH_HOME'] == str(root / 'torch')

from tts_builder.gui.settings import normalize_model_root, should_update_current_output


def test_normalize_model_root_accepts_huggingface_cache_levels(tmp_path: Path):
    root = tmp_path / 'AI-cache'
    assert normalize_model_root(root) == root
    assert normalize_model_root(root / 'huggingface') == root
    assert normalize_model_root(root / 'huggingface' / 'hub') == root
    repo = root / 'huggingface' / 'hub' / 'models--org--model'
    assert normalize_model_root(repo) == root


def test_default_output_change_does_not_override_task_specific_output(tmp_path: Path):
    old_default = tmp_path / 'default-old'
    new_default = tmp_path / 'default-new'
    current_task = tmp_path / 'speaker-acane'
    assert not should_update_current_output(current_task, old_default)
    assert should_update_current_output(old_default, old_default)
