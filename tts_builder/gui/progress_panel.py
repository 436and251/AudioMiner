from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from .models import ProgressModel, STAGES
from .styles import FAILED, GREEN, MUTED, PENDING

_LABELS = {
    "prepare": "Prepare",
    "source": "Source",
    "separate": "Vocal separation",
    "normalize": "Normalize",
    "asr": "ASR transcription",
    "segment": "Segment",
    "export": "Export",
}


class ProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        for row, stage in enumerate(STAGES):
            icon = QLabel("○")
            name = QLabel(_LABELS[stage])
            status = QLabel("Waiting")
            status.setStyleSheet(f"color:{MUTED}")
            grid.addWidget(icon, row, 0)
            grid.addWidget(name, row, 1)
            grid.addWidget(status, row, 2)
            self.rows[stage] = (icon, status)
        self.total = QProgressBar()
        self.total.setRange(0, 100)
        self.total.setValue(0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(grid)
        layout.addSpacing(8)
        layout.addWidget(self.total)

    def apply(self, model: ProgressModel) -> None:
        for stage, state in model.stages.items():
            icon, label = self.rows[stage]
            if state.status in {"completed", "cached"}:
                icon.setText("✓")
                icon.setStyleSheet(f"color:{GREEN};font-weight:700")
                label.setText(state.message or ("Cached" if state.status == "cached" else "Done"))
            elif state.status == "running":
                icon.setText("●")
                icon.setStyleSheet(f"color:{GREEN}")
                label.setText(state.message or (f"{state.percent}%" if state.percent else "Working…"))
            elif state.status == "failed":
                icon.setText("!")
                icon.setStyleSheet(f"color:{FAILED};font-weight:700")
                label.setText(state.message or "Failed")
            else:
                icon.setText("○")
                icon.setStyleSheet(f"color:{PENDING}")
                label.setText("Waiting")
            label.setStyleSheet(f"color:{MUTED}")
        self.total.setValue(model.overall_percent)
