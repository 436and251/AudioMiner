from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QPlainTextEdit, QToolButton, QVBoxLayout, QWidget

from ..events import PipelineEvent


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.toggle = QToolButton(text="▸ Activity")
        self.toggle.setCheckable(True)
        self.toggle.toggled.connect(self._toggle)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(800)
        self.view.setVisible(False)
        self.view.setMaximumHeight(170)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.view)

    def _toggle(self, checked: bool) -> None:
        self.toggle.setText(("▾" if checked else "▸") + " Activity")
        self.view.setVisible(checked)

    def append_event(self, event: PipelineEvent) -> None:
        if not event.message:
            return
        stage = f"[{event.stage}] " if event.stage else ""
        self.append_text(f"{stage}{event.message}")

    def append_text(self, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.view.appendPlainText(f"{stamp}  {text}")
