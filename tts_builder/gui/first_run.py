from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .settings import AppSettings
from .styles import GREEN, MUTED
from .system_check import detect_system, recommendation_for


class FirstRunDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Voice Dataset Builder")
        self.setMinimumWidth(620)
        self.info = detect_system(settings.model_root)
        self.recommendation = recommendation_for(self.info)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(16)
        title = QLabel("Voice Dataset Builder")
        title.setObjectName("Title")
        subtitle = QLabel("Prepare clean, timestamped voice datasets locally.")
        subtitle.setObjectName("Subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("Card")
        rows = QVBoxLayout(card)
        rows.setContentsMargins(18, 16, 18, 16)
        gpu = self.info.gpu_name if self.info.cuda_available else "CPU mode"
        rows.addWidget(self._status("Acceleration", gpu, self.info.cuda_available))
        rows.addWidget(self._status("Memory", f"{self.info.ram_gb:.1f} GB", self.info.ram_gb >= 8))
        rows.addWidget(self._status("FFmpeg", "Ready" if self.info.ffmpeg_available else "Not found", self.info.ffmpeg_available))
        rows.addWidget(self._status("Model storage", f"{self.info.free_gb:.0f} GB free", self.info.free_gb >= 5))
        layout.addWidget(card)

        note = QLabel(
            "Before you start\n\n"
            "• AI models need several GB of storage and the first download can take time.\n"
            "• NVIDIA CUDA is recommended. CPU mode is supported but significantly slower.\n"
            "• Model and online-media downloads require internet access and can resume after interruption.\n"
            "• Audio processing and generated datasets stay on this computer."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED}; line-height:1.4")
        layout.addWidget(note)

        self.path_label = QLabel(str(self.settings.model_root))
        self.path_label.setStyleSheet(f"color:{MUTED}")
        change = QPushButton("Change")
        change.clicked.connect(self._change_root)
        row = QHBoxLayout()
        row.addWidget(QLabel("Model storage"))
        row.addWidget(self.path_label, 1)
        row.addWidget(change)
        layout.addLayout(row)
        layout.addStretch(1)
        button = QPushButton("Continue  →")
        button.setObjectName("Primary")
        button.clicked.connect(self.accept)
        layout.addWidget(button)

    def _status(self, name: str, value: str, good: bool) -> QLabel:
        icon = "●" if good else "○"
        color = GREEN if good else "#E6B450"
        label = QLabel(f"{icon}  {name}    {value}")
        label.setStyleSheet(f"color:{color if name == 'Acceleration' else '#FFFFFF'}")
        return label

    def _change_root(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose model storage", str(self.settings.model_root))
        if chosen:
            self.settings = replace(self.settings, model_root=Path(chosen))
            self.path_label.setText(chosen)

    def result_settings(self) -> AppSettings:
        model = self.settings.preferred_asr_model
        if not self.info.cuda_available and model == "large-v3-turbo":
            model = self.recommendation.asr_model
        return replace(self.settings, first_run_completed=True, preferred_asr_model=model)
