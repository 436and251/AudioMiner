from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from .model_manager import is_asr_model_ready
from .settings import AppSettings, model_cache_paths, normalize_model_root
from .styles import MUTED


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        form = QFormLayout()
        self.model_root = QLineEdit(str(settings.model_root))
        self.output_root = QLineEdit(str(settings.output_root))
        self.model = QComboBox()
        self.model.addItems(["large-v3-turbo", "small", "large-v3"])
        self.model.setCurrentText(settings.preferred_asr_model)
        form.addRow("Model storage root", self._path_row(self.model_root, "model"))
        self.model_paths_hint = QLabel()
        self.model_paths_hint.setWordWrap(True)
        self.model_paths_hint.setStyleSheet(f"color:{MUTED}")
        form.addRow("", self.model_paths_hint)
        hint = QLabel("Changing this location does not move existing models automatically.")
        hint.setStyleSheet(f"color:{MUTED}")
        form.addRow("", hint)
        form.addRow("Default output directory", self._path_row(self.output_root, "output"))
        form.addRow("Default ASR model", self.model)
        self.ready = QLabel()
        form.addRow("Model status", self.ready)
        self.model.currentTextChanged.connect(self._update_ready)
        self.model_root.textChanged.connect(self._update_ready)
        self.model_root.textChanged.connect(self._update_model_paths_hint)
        layout.addLayout(form)
        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        save.setObjectName("Primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        self._update_ready()
        self._update_model_paths_hint()

    def _path_row(self, edit: QLineEdit, kind: str):
        box = QHBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("Browse")
        button.clicked.connect(lambda: self._browse(edit))
        box.addWidget(edit, 1)
        box.addWidget(button)
        from PySide6.QtWidgets import QWidget
        container = QWidget()
        container.setLayout(box)
        return container

    def _browse(self, edit: QLineEdit) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose folder", edit.text())
        if chosen:
            chosen_path = Path(chosen)
            if edit is self.model_root:
                chosen_path = normalize_model_root(chosen_path)
            edit.setText(str(chosen_path))

    def _update_ready(self, *_) -> None:
        root = normalize_model_root(Path(self.model_root.text()).expanduser())
        hf_home, _ = model_cache_paths(root)
        self.ready.setText("Ready" if is_asr_model_ready(self.model.currentText(), hf_home) else "Not downloaded")

    def _update_model_paths_hint(self, *_) -> None:
        root = normalize_model_root(Path(self.model_root.text()).expanduser())
        hf_home, torch_home = model_cache_paths(root)
        self.model_paths_hint.setText(
            f"Hugging Face: {hf_home}\nDemucs: {torch_home}"
        )

    def result_settings(self) -> AppSettings:
        return replace(
            self.settings,
            model_root=normalize_model_root(Path(self.model_root.text()).expanduser()),
            output_root=Path(self.output_root.text()).expanduser(),
            preferred_asr_model=self.model.currentText(),
        )
