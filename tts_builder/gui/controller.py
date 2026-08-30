from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..config import BuildConfig
from ..events import CancellationToken, PipelineCancelled, PipelineEvent
from ..pipeline import process_source
from .model_manager import friendly_download_error, friendly_task_error, prepare_asr_model, prepare_demucs_model
from .preflight import check_runtime


class _Worker(QObject):
    event = Signal(object)
    completed = Signal(object)
    failed = Signal(str, str, str)
    cancelled = Signal()
    finished = Signal()

    def __init__(self, source: str, config: BuildConfig, token: CancellationToken):
        super().__init__()
        self.source = source
        self.config = config
        self.token = token

    def _emit(self, event: PipelineEvent) -> None:
        self.event.emit(event)

    @Slot()
    def run(self) -> None:
        try:
            self._emit(PipelineEvent("stage_started", "prepare", "Checking models and runtime"))
            try:
                check_runtime(self.config.output)
                model_path = prepare_asr_model(self.config.asr_model, self._emit, self.token)
                if not self.config.skip_separation:
                    prepare_demucs_model(self.config.separator_model, self._emit, self.token)
            except PipelineCancelled:
                raise
            except Exception as exc:
                title, message = friendly_download_error(exc)
                self._emit(PipelineEvent("stage_failed", "prepare", message))
                self.failed.emit(title, message, str(exc))
                return
            self._emit(PipelineEvent("stage_completed", "prepare", "Ready"))
            runtime_config = replace(self.config, asr_model_path=str(model_path))
            summary = process_source(self.source, runtime_config, self._emit, self.token)
            self.completed.emit(summary)
        except PipelineCancelled:
            self.cancelled.emit()
        except Exception as exc:
            title, message = friendly_task_error(exc)
            self.failed.emit(title, message, repr(exc))
        finally:
            self.finished.emit()


class TaskController(QObject):
    event_received = Signal(object)
    task_completed = Signal(object)
    task_failed = Signal(str, str, str)
    task_cancelled = Signal()
    running_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None
        self._token = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self, source: str, config: BuildConfig) -> None:
        if self.running:
            raise RuntimeError("a task is already running")
        self._token = CancellationToken()
        self._thread = QThread(self)
        self._worker = _Worker(source, config, self._token)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.event.connect(self.event_received)
        self._worker.completed.connect(self.task_completed)
        self._worker.failed.connect(self.task_failed)
        self._worker.cancelled.connect(self.task_cancelled)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._on_finished)
        self.running_changed.emit(True)
        self._thread.start()

    def stop(self) -> None:
        if self._token:
            self._token.cancel()

    @Slot()
    def _on_finished(self) -> None:
        if self._thread:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self._token = None
        self.running_changed.emit(False)
