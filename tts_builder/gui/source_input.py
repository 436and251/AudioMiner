from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget


class SourceInput(QWidget):
    source_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Paste a media URL or choose a local audio/video file")
        self.edit.textChanged.connect(self.source_changed)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.edit, 1)
        row.addWidget(browse)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(row)

    def value(self) -> str:
        return self.edit.text().strip()

    def set_value(self, value: str) -> None:
        self.edit.setText(value)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose media", "", "Media files (*.wav *.mp3 *.m4a *.flac *.mp4 *.mkv *.mov *.webm);;All files (*)"
        )
        if path:
            self.set_value(path)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        url = event.mimeData().urls()[0]
        if url.isLocalFile() and Path(url.toLocalFile()).is_file():
            self.set_value(url.toLocalFile())
            event.acceptProposedAction()
