from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QVBoxLayout, QWidget, QToolButton
)

from ..config import BuildConfig
from ..events import PipelineEvent
from .controller import TaskController
from .log_panel import LogPanel
from .model_manager import estimated_asr_bytes, is_asr_model_ready
from .models import ProgressModel
from .progress_panel import ProgressPanel
from .settings import AppSettings, apply_model_environment, should_update_current_output
from .settings_dialog import SettingsDialog
from .source_input import SourceInput
from .styles import FAILED, MUTED


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, controller: TaskController | None = None):
        super().__init__()
        self.settings = settings
        self.controller = controller or TaskController(self)
        self.progress_model = ProgressModel()
        self.setWindowTitle("Voice Dataset Builder")
        self.resize(860, 760)
        self.setMinimumSize(760, 650)
        self._build()
        self._wire()
        self._validate()

    def _build(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(16)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Voice Dataset Builder")
        title.setObjectName("Title")
        subtitle = QLabel("Turn media into a clean GPT-SoVITS training dataset")
        subtitle.setObjectName("Subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        self.settings_btn = QToolButton()
        self.settings_btn.setObjectName("IconButton")
        self.settings_btn.setText("⚙")
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setFixedSize(44, 44)
        self.settings_btn.clicked.connect(self._open_settings)
        header.addLayout(titles, 1)
        header.addWidget(self.settings_btn)
        layout.addLayout(header)

        card = QFrame()
        card.setObjectName("Card")
        form = QVBoxLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(12)
        self.source = SourceInput()
        form.addWidget(self.source)
        row = QHBoxLayout()
        self.speaker = QLineEdit()
        self.speaker.setPlaceholderText("Speaker · e.g. suis")
        self.language = QComboBox()
        self.language.addItem("Auto", "auto")
        self.language.addItem("Japanese", "ja")
        self.language.addItem("Chinese", "zh")
        self.language.addItem("English", "en")
        self.model = QComboBox()
        self.model.addItems(["large-v3-turbo", "small", "large-v3"])
        self.model.setCurrentText(self.settings.preferred_asr_model)
        row.addWidget(self.speaker, 2)
        row.addWidget(self.language, 1)
        row.addWidget(self.model, 1)
        form.addLayout(row)
        out = QHBoxLayout()

        self.output_label = QLabel("Output directory")
        self.output_label.setObjectName("FieldChip")
        self.output_label.setAlignment(Qt.AlignCenter)
        self.output_label.setFixedWidth(140)

        self.output = QLineEdit(str(self.settings.output_root))

        self.output_browse = QPushButton("Browse")
        self.output_browse.clicked.connect(self._browse_output)

        out.addWidget(self.output_label)
        out.addWidget(self.output, 1)
        out.addWidget(self.output_browse)

        form.addLayout(out)
        layout.addWidget(card)

        actions = QHBoxLayout()
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{MUTED}")
        self.open_output = QPushButton("Open output")
        self.open_output.clicked.connect(self._open_output)
        self.stop = QPushButton("Stop")
        self.stop.setObjectName("Danger")
        self.stop.clicked.connect(self._stop)
        self.start = QPushButton("▶  Build Dataset")
        self.start.setObjectName("Primary")
        self.start.clicked.connect(self._start)
        actions.addWidget(self.status, 1)
        actions.addWidget(self.open_output)
        actions.addWidget(self.stop)
        actions.addWidget(self.start)
        layout.addLayout(actions)

        progress_card = QFrame()
        progress_card.setObjectName("Card")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(18, 16, 18, 16)
        progress_layout.addWidget(QLabel("Processing"))
        self.progress = ProgressPanel()
        progress_layout.addWidget(self.progress)
        layout.addWidget(progress_card)
        self.logs = LogPanel()
        layout.addWidget(self.logs)
        layout.addStretch(1)
        self.setCentralWidget(root)

    def _wire(self) -> None:
        self.source.source_changed.connect(self._validate)
        self.speaker.textChanged.connect(self._validate)
        self.controller.event_received.connect(self._event)
        self.controller.task_completed.connect(self._completed)
        self.controller.task_failed.connect(self._failed)
        self.controller.task_cancelled.connect(self._cancelled)
        self.controller.running_changed.connect(self._running)

    def _validate(self, *_) -> None:
        self.start.setEnabled(bool(self.source.value() and self.speaker.text().strip()) and not self.controller.running)

    def _config(self) -> BuildConfig:
        return BuildConfig(
            output=Path(self.output.text()).expanduser(), speaker=self.speaker.text().strip(),
            language=str(self.language.currentData()), asr_model=self.model.currentText(),
        )

    def _start(self) -> None:
        config = self._config()
        if not is_asr_model_ready(config.asr_model, self.settings.model_root / "huggingface"):
            size = estimated_asr_bytes(config.asr_model)
            size_text = f"~{size / 1e9:.1f} GB" if size else "several hundred MB"
            box = QMessageBox(self)
            box.setWindowTitle("Prepare AI models")
            box.setText(f"{config.asr_model} is not installed yet.")
            box.setInformativeText(
                f"The first run will download {size_text} for Whisper, plus Demucs model data when needed.\n\n"
                f"Model storage:\n{self.settings.model_root}\n\nInterrupted downloads keep their cache and can be retried."
            )
            box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
            box.button(QMessageBox.Ok).setText("Download & Continue")
            if box.exec() != QMessageBox.Ok:
                return
        self.progress_model = ProgressModel()
        self.progress.apply(self.progress_model)
        self.start.setText("▶  Build Dataset")
        self.status.setStyleSheet(f"color:{MUTED}")
        self.status.setText("Preparing…")
        self.controller.start(self.source.value(), config)

    def _event(self, event: PipelineEvent) -> None:
        self.progress_model.consume(event)
        self.progress.apply(self.progress_model)
        self.logs.append_event(event)
        if event.stage and event.message:
            self.status.setText(event.message)

    def _running(self, running: bool) -> None:
        self.source.setEnabled(not running)
        self.speaker.setEnabled(not running)
        self.language.setEnabled(not running)
        self.model.setEnabled(not running)
        self.output.setEnabled(not running)
        self.output_browse.setEnabled(not running)
        self.settings_btn.setEnabled(not running)
        self.stop.setEnabled(running)
        self._validate()

    def _completed(self, summary) -> None:
        self.status.setStyleSheet(f"color:{MUTED}")
        self.status.setText(f"Ready · {summary.accepted} accepted · {summary.rejected} rejected")
        self.start.setText("▶  Build Dataset")

    def _failed(self, title: str, message: str, detail: str) -> None:
        self.status.setStyleSheet(f"color:{FAILED}")
        self.status.setText(message)
        self.logs.append_text(detail)
        self.start.setText("↻  Retry")
        box = QMessageBox(QMessageBox.Critical, title, message, QMessageBox.Ok, self)
        box.setDetailedText(detail)
        box.exec()

    def _cancelled(self) -> None:
        self.status.setText("Stopped · completed cache was preserved")

    def _stop(self) -> None:
        self.status.setText("Stopping after the current safe point…")
        self.controller.stop()

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose dataset output", self.output.text())
        if path:
            self.output.setText(path)

    def _open_output(self) -> None:
        path = Path(self.output.text()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _open_settings(self) -> None:
        old_settings = self.settings
        current_output = Path(self.output.text()).expanduser()
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            new_settings = dialog.result_settings()
            self.settings = new_settings
            self.settings.save()
            apply_model_environment(self.settings.model_root)
            if should_update_current_output(current_output, old_settings.output_root):
                self.output.setText(str(self.settings.output_root))
            self.model.setCurrentText(self.settings.preferred_asr_model)
