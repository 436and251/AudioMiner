# Desktop GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Spotify-inspired PySide6 desktop GUI and Windows onedir executable packaging around frozen V2.3 without duplicating or changing dataset semantics.

**Architecture:** The core pipeline gains a tiny optional event/cancellation contract. A QThread-based GUI controller invokes the same `process_source` function and renders structured events into stage/progress/log widgets. Packaging uses PyInstaller onedir; bundled binary resolution and Demucs invocation are made freeze-safe while preserving existing core interfaces and compact cache behavior.

**Tech Stack:** Python 3.12, PySide6, pytest, PyInstaller, existing faster-whisper/Demucs/FFmpeg stack.

**Spec:** `docs/superpowers/specs/2026-08-27-desktop-gui-design.md`

## Global Constraints

- Frozen V2.3 dataset semantics and compact cache policy must remain unchanged.
- Existing `build_dataset.py` CLI remains usable without importing PySide6.
- GUI V1 accepts one source per task.
- Windows release uses PyInstaller `onedir`, not `onefile`.
- Model weights remain external in Hugging Face/PyTorch caches; they are not embedded in the EXE.
- No Spotify logo, trademarked artwork, or proprietary assets are bundled.
- Production Python files should remain approximately <=200 lines where practical.
- Use TDD for all production behavior changes.

---

### Task 1: Core Pipeline Event and Cancellation Contract

**Files:**
- Create: `tts_builder/events.py`
- Modify: `tts_builder/pipeline.py`
- Test: `tests/test_events.py`
- Test: `tests/test_pipeline_events.py`

**Interfaces:**
- Produces: `PipelineEvent`, `EventSink`, `CancellationToken`, `PipelineCancelled`, `emit(sink, event)`.
- Produces: `process_source(source: str, config: BuildConfig, event_sink: EventSink | None = None, cancel_token: CancellationToken | None = None) -> ProcessSummary`.
- Existing two-argument `process_source(source, config)` remains valid.

- [ ] **Step 1: Write failing event primitive tests**

```python
from tts_builder.events import CancellationToken, PipelineCancelled, PipelineEvent


def test_cancellation_token_raises_after_cancel():
    token = CancellationToken()
    token.cancel()
    try:
        token.raise_if_cancelled()
    except PipelineCancelled:
        return
    raise AssertionError("expected PipelineCancelled")


def test_pipeline_event_defaults_are_safe():
    event = PipelineEvent(kind="log", message="hello")
    assert event.stage is None
    assert event.metadata == {}
```

- [ ] **Step 2: Run event tests and verify RED**

Run: `pytest tests/test_events.py -v`
Expected: FAIL because `tts_builder.events` does not exist.

- [ ] **Step 3: Implement minimal event primitives**

Create dataclass/protocol/token exactly as specified in the design. `emit(None, event)` is a no-op.

- [ ] **Step 4: Run event tests and verify GREEN**

Run: `pytest tests/test_events.py -v`
Expected: PASS.

- [ ] **Step 5: Write failing pipeline event-order test**

Use monkeypatch for acquisition/separation/ASR/output so no heavy dependency runs. Capture events in a list and assert the successful path begins with `pipeline_started`, emits `stage_started`/`stage_completed`, and ends with `pipeline_completed`. Add a cancellation case that cancels before ASR and asserts `pipeline_cancelled`/`PipelineCancelled` without marking ASR completed.

- [ ] **Step 6: Run pipeline event tests and verify RED**

Run: `pytest tests/test_pipeline_events.py -v`
Expected: FAIL because `process_source` does not accept event/cancel arguments or emit events.

- [ ] **Step 7: Add optional event/cancel wiring to `pipeline.py`**

Add helper functions rather than scattering raw sink calls. Check cancellation before/after each stage. Emit cache-hit events from existing cache branches. Keep existing prints for now so CLI output is unchanged.

- [ ] **Step 8: Run focused and existing pipeline tests**

Run: `pytest tests/test_pipeline_events.py tests/test_pipeline.py tests/test_resume_cache.py -v`
Expected: PASS.

---

### Task 2: Instrument Long-Running Operations and Make Runtime Binary Resolution Freeze-Safe

**Files:**
- Create: `tts_builder/runtime.py`
- Modify: `tts_builder/media.py`
- Modify: `tts_builder/transcriber.py`
- Modify: `tts_builder/sources/download.py`
- Modify: `tts_builder/sources/http_download.py`
- Modify: `tts_builder/sources/resumable.py`
- Test: `tests/test_runtime.py`
- Test: `tests/test_operation_events.py`

**Interfaces:**
- Produces: `resolve_binary(name: str) -> str`.
- Existing public functions retain their current positional/default behavior, gaining optional keyword-only `event_sink=None` and `cancel_token=None` where needed.

- [ ] **Step 1: Write failing runtime binary resolution tests**

Cover bundled `bin/ffmpeg.exe` preference and PATH fallback using monkeypatch of `sys.executable`, frozen marker, filesystem, and `shutil.which`.

- [ ] **Step 2: Run runtime tests and verify RED**

Run: `pytest tests/test_runtime.py -v`
Expected: FAIL because `tts_builder.runtime` does not exist.

- [ ] **Step 3: Implement `resolve_binary` and update FFmpeg normalization**

Use application directory when frozen, then PATH. `normalize_audio` invokes returned FFmpeg path. Preserve current error semantics with a clearer message.

- [ ] **Step 4: Write failing progress/cancellation tests for download and ASR iteration**

Use fake HTTP chunks and fake Whisper segment iterator. Assert byte progress event values increase monotonically and cancellation stops iteration before later segments are consumed.

- [ ] **Step 5: Run operation tests and verify RED**

Run: `pytest tests/test_operation_events.py -v`
Expected: FAIL because optional event/cancel wiring is absent.

- [ ] **Step 6: Add optional progress/cancellation hooks**

Emit trustworthy byte progress from download chunks. In transcriber, emit progress using segment end timestamps when audio duration is known or emit log/current values without fabricating total. Check cancellation between yielded segments.

- [ ] **Step 7: Run focused tests**

Run: `pytest tests/test_runtime.py tests/test_operation_events.py tests/test_sources.py -v`
Expected: PASS.

---

### Task 3: Freeze-Safe and Cancellable Demucs Runner

**Files:**
- Modify: `tts_builder/separator.py`
- Create: `tts_builder/demucs_runner.py`
- Test: `tests/test_separator.py`
- Test: `tests/test_demucs_runner.py`

**Interfaces:**
- `separate_vocals(...) -> Path` remains unchanged for existing callers; optional event/cancel keywords are allowed.
- Produces: `run_demucs(input_path, output_root, model, device, segment_seconds, event_sink=None, cancel_token=None) -> None`.

- [ ] **Step 1: Write failing tests for frozen runner selection**

Monkeypatch the Demucs runner and assert `separate_vocals` no longer relies on `sys.executable -m demucs` in frozen mode while still returning the detected `vocals.flac` path.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/test_demucs_runner.py tests/test_separator.py -v`
Expected: FAIL for missing runner behavior.

- [ ] **Step 3: Implement Demucs callable runner**

Use Demucs' importable Python entry/API behind `demucs_runner.py`. Keep all Demucs-specific import details in that file. Check cancellation before start and after return; if the chosen API provides callbacks/process control, wire them without changing output structure.

- [ ] **Step 4: Verify separator tests**

Run: `pytest tests/test_demucs_runner.py tests/test_separator.py -v`
Expected: PASS.

---

### Task 4: GUI Controller and Progress Model

**Files:**
- Create: `requirements-gui.txt`
- Create: `tts_builder/gui/__init__.py`
- Create: `tts_builder/gui/models.py`
- Create: `tts_builder/gui/controller.py`
- Test: `tests/gui/test_controller.py`
- Test: `tests/gui/test_progress_model.py`

**Interfaces:**
- Produces: `TaskController.start(source: str, config: BuildConfig)`, `TaskController.stop()`.
- Qt signals: `event_received(object)`, `task_completed(object)`, `task_failed(str)`, `task_cancelled()`, `running_changed(bool)`.
- Produces a pure-Python `ProgressModel` that consumes `PipelineEvent` and returns stage/overall view state.

- [ ] **Step 1: Add PySide6 GUI requirement**

`requirements-gui.txt` contains `PySide6>=6.8,<7` and references/notes that core requirements must also be installed.

- [ ] **Step 2: Write failing pure progress model tests**

Assert stage weights sum to 1.0; cache-hit contributes full stage weight; indeterminate active stage does not invent fine-grained percentage; completed six-stage path reaches 100%.

- [ ] **Step 3: Run progress tests and verify RED**

Run: `pytest tests/gui/test_progress_model.py -v`
Expected: FAIL because GUI model does not exist.

- [ ] **Step 4: Implement progress model**

Keep this module free of PySide6 so it is easy to test.

- [ ] **Step 5: Write failing controller tests**

With `QT_QPA_PLATFORM=offscreen`, monkeypatch `process_source` to emit events and return/fail/cancel. Use Qt event processing to assert signal paths and one-active-task behavior.

- [ ] **Step 6: Run controller tests and verify RED**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/gui/test_controller.py -v`
Expected: FAIL because controller does not exist.

- [ ] **Step 7: Implement QThread worker/controller**

Worker creates a `CancellationToken`, invokes the core on its thread, forwards core events through Qt signals, and guarantees `running_changed(False)` on all terminal paths.

- [ ] **Step 8: Run GUI controller tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/gui/test_progress_model.py tests/gui/test_controller.py -v`
Expected: PASS.

---

### Task 5: Spotify-Inspired GUI Components

**Files:**
- Create: `tts_builder/gui/styles.py`
- Create: `tts_builder/gui/source_input.py`
- Create: `tts_builder/gui/settings_panel.py`
- Create: `tts_builder/gui/progress_panel.py`
- Create: `tts_builder/gui/log_panel.py`
- Test: `tests/gui/test_source_input.py`
- Test: `tests/gui/test_widgets.py`

**Interfaces:**
- `SourceInput.value() -> str`, signal `source_changed(str)`.
- `SettingsPanel.build_config() -> BuildConfig` after validation.
- `ProgressPanel.apply(model_state) -> None`.
- `LogPanel.append_event(event) -> None`.

- [ ] **Step 1: Write failing source input tests**

Test URL text, local Browse-value setter helper, and drag/drop of one local file using offscreen Qt.

- [ ] **Step 2: Run source input tests and verify RED**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/gui/test_source_input.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement source input card and styles**

Use near-black surfaces, rounded input, green focus/action accent. No webview and no external visual assets.

- [ ] **Step 4: Write failing widget default/state tests**

Assert language defaults to Auto, ASR defaults to `large-v3-turbo`, six stage rows exist in order, log panel is collapsible and bounded.

- [ ] **Step 5: Run tests and verify RED**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/gui/test_widgets.py -v`
Expected: FAIL.

- [ ] **Step 6: Implement settings/progress/log components**

Keep each widget focused and approximately <=200 lines.

- [ ] **Step 7: Run widget tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/gui/test_source_input.py tests/gui/test_widgets.py -v`
Expected: PASS.

---

### Task 6: Main Window and Development Launcher

**Files:**
- Create: `tts_builder/gui/main_window.py`
- Create: `tts_builder/gui/app.py`
- Create: `voice_dataset_builder.py`
- Test: `tests/gui/test_main_window.py`

**Interfaces:**
- `create_application(argv=None) -> QApplication`.
- `MainWindow(controller: TaskController | None = None)`.

- [ ] **Step 1: Write failing main-window behavior tests**

Assert Start disabled until source+speaker are valid; Start invokes controller with a `BuildConfig`; running state disables inputs and enables Stop; completion shows accepted/rejected summary; failure exposes concise error and logs details.

- [ ] **Step 2: Run tests and verify RED**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/gui/test_main_window.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement main window composition**

Compose existing focused widgets; do not duplicate their rendering logic. Wire Open Output using `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` for portability.

- [ ] **Step 4: Implement GUI launcher**

`voice_dataset_builder.py` imports `tts_builder.gui.app.main` only and exits with its return code.

- [ ] **Step 5: Run GUI tests and import smoke tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/gui -v`
Run: `python -c "import tts_builder.cli; print('cli import ok')"`
Run: `python -c "import tts_builder.gui.app; print('gui import ok')"`
Expected: all PASS and both import messages print.

---

### Task 7: Preserve CLI Behavior While Sharing Events

**Files:**
- Modify: `tts_builder/cli.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_pipeline_events.py`

**Interfaces:**
- CLI still returns 0 on all successes and 1 if any source fails.
- Existing flags remain unchanged.

- [ ] **Step 1: Add failing regression tests for CLI without PySide6 import**

Patch Python import machinery or inspect `sys.modules` after importing `tts_builder.cli`; assert no `PySide6` module is required for CLI import.

- [ ] **Step 2: Run CLI tests and verify expected state**

Run: `pytest tests/test_cli.py -v`
Expected: new assertion fails only if GUI dependencies leaked into core/CLI.

- [ ] **Step 3: Add a small CLI event renderer only if needed**

If core operation instrumentation replaced direct prints, render equivalent text from events here. Do not introduce GUI imports.

- [ ] **Step 4: Run CLI/core regression**

Run: `pytest tests/test_cli.py tests/test_pipeline.py tests/test_resume_cache.py tests/test_sources.py -v`
Expected: PASS.

---

### Task 8: Windows Onedir Packaging

**Files:**
- Create: `requirements-build.txt`
- Create: `VoiceDatasetBuilder.spec`
- Create: `scripts/build_windows.ps1`
- Create: `vendor/ffmpeg/README.md`
- Modify: `.gitignore`
- Test: `tests/test_packaging_config.py`

**Interfaces:**
- Build command: `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`.
- Output: `dist/VoiceDatasetBuilder/VoiceDatasetBuilder.exe`.

- [ ] **Step 1: Write failing packaging config tests**

Parse/check that the spec uses `console=False`, name `VoiceDatasetBuilder`, onedir COLLECT output, includes `tts_builder.gui`, and declares collection for Demucs/faster-whisper/PySide6 as required.

- [ ] **Step 2: Run packaging tests and verify RED**

Run: `pytest tests/test_packaging_config.py -v`
Expected: FAIL because spec/build files do not exist.

- [ ] **Step 3: Add build requirements and PyInstaller spec**

`requirements-build.txt` pins a compatible PyInstaller major range. The spec collects package data/hidden imports needed by torch, demucs, ctranslate2/faster-whisper, and PySide6 using PyInstaller hooks/`collect_all` selectively.

- [ ] **Step 4: Add Windows build script**

Script verifies it is running on Windows, runs tests, invokes PyInstaller, copies `vendor/ffmpeg/ffmpeg.exe` and `ffprobe.exe` into `dist/VoiceDatasetBuilder/bin/` if present, and prints the final executable path. It must fail clearly if packaging fails.

- [ ] **Step 5: Add vendor FFmpeg instructions and ignore build outputs**

Document that FFmpeg binaries are not committed in this source package and where to place them before a self-contained release build.

- [ ] **Step 6: Run packaging config tests**

Run: `pytest tests/test_packaging_config.py -v`
Expected: PASS.

- [ ] **Step 7: On a Windows build environment, build and launch smoke test**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`
Expected: exit 0 and `dist\VoiceDatasetBuilder\VoiceDatasetBuilder.exe` exists. Launch it and verify the main window opens. This platform-specific step cannot be considered verified from a non-Windows builder.

---

### Task 9: Documentation and Full Verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- README documents both GUI and CLI without implying the Windows EXE is already prebuilt when only source is distributed.

- [ ] **Step 1: Update README**

Document GUI development run:

```powershell
uv pip install -r requirements.txt
uv pip install -r requirements-gui.txt
python voice_dataset_builder.py
```

Document Windows build prerequisites, external model caches, compact resume behavior, and CLI compatibility.

- [ ] **Step 2: Run the complete automated test suite**

Run on development environment:

```bash
QT_QPA_PLATFORM=offscreen pytest -q
python -m compileall -q tts_builder build_dataset.py voice_dataset_builder.py
python build_dataset.py -h
```

Expected: all tests PASS, compileall exits 0, CLI help exits 0.

- [ ] **Step 3: Check production file sizes**

Run a line-count command over `tts_builder/**/*.py`; if a new GUI file substantially exceeds ~200 lines, split it by responsibility before completion.

- [ ] **Step 4: Compare equivalent CLI/GUI output semantics**

Using mocked/lightweight pipeline fixtures, assert equivalent `BuildConfig` produces the same summary and export paths regardless of CLI or GUI caller.


## Approved implementation addendum: light first run

The user approved these additional V1 requirements after the original plan:

- Add `tts_builder/gui/settings.py` for persistent first-run/model/output preferences and automatic `HF_HOME`/`TORCH_HOME` mapping.
- Add `tts_builder/gui/system_check.py` and `first_run.py`; first launch performs local checks only and never downloads models.
- Add `tts_builder/gui/model_manager.py`; the Prepare stage verifies/downloads Whisper and Demucs models only after Build is requested.
- Cached Whisper snapshots are returned locally without contacting Hugging Face, enabling offline local processing.
- Model-download failures are classified into user-facing network/storage/preparation errors while retaining technical detail.
- Settings expose model storage, dataset output, default ASR model, and model readiness; low-level CDN/timeout/compute parameters stay hidden.
