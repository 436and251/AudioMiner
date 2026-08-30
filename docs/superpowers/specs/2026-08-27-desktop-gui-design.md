# Voice Dataset Builder Desktop GUI Design

## Status
Approved direction from chat on 2026-08-27; written specification for implementation review.

## Goal
Add a lightweight desktop GUI to frozen V2.3 so a non-technical user can launch the tool from one Windows executable entry point, select a local media file or paste a web URL, run the existing dataset-building pipeline, and see stage progress and logs in a Spotify-inspired dark/green interface.

## Scope

### Included in V1 GUI
- Windows-first desktop application built with PySide6.
- Shared source code remains portable to macOS/Linux; packaging is platform-specific.
- URL input and local audio/video file picker/drag-and-drop.
- Speaker, language, ASR model, output directory.
- Start and cooperative Stop controls.
- Six visible pipeline stages: Source, Vocal Separation, Normalize, ASR, Segment, Export.
- Overall progress plus current stage status.
- Collapsible activity log.
- Cache/resume status surfaced in the UI.
- Open output folder action.
- Existing CLI remains available and behavior-compatible.
- Windows onedir executable distribution: user launches one `VoiceDatasetBuilder.exe`; dependency files stay hidden in the application directory.

### Explicitly excluded
- Audio waveform editor or manual segmentation.
- Built-in audio player.
- Account/login management.
- Cookie management UI.
- Training/fine-tuning UI.
- Multiple cache levels.
- Theme editor.
- Single-file PyInstaller bundle.
- Background service or web server.

## Visual Direction
Inspired by the provided Spotify-style reference, without copying Spotify branding or proprietary assets.

- Main background: near-black `#121212`.
- Raised surfaces: `#181818` and `#242424`.
- Primary accent: `#1ED760`-like green.
- Primary text: white; secondary text: muted gray around `#B3B3B3`.
- Rounded cards and pill inputs/buttons.
- Green is reserved for primary action, active progress, cache hit/completion states.
- System font stack: Segoe UI / Microsoft YaHei on Windows; platform-native fallback elsewhere.
- Window defaults around 820x620 and supports resize; minimum 720x540.
- Custom dark title region is allowed, but native minimize/maximize/close behavior must remain reliable.

## Architecture

```text
Desktop UI (PySide6)
        |
        | Qt signals / typed progress events
        v
TaskController + PipelineWorker (QThread)
        |
        | BuildConfig + EventSink + CancellationToken
        v
Frozen V2.3 pipeline behavior
        |
        +-- source acquisition/cache
        +-- Demucs
        +-- normalize/ffmpeg
        +-- faster-whisper
        +-- segmentation/export
```

The GUI does not duplicate pipeline logic. The core gains a minimal optional event/cancellation interface. With no event sink supplied, CLI behavior remains unchanged.

## Core Event Contract

Create `tts_builder/events.py`:

```python
@dataclass(frozen=True)
class PipelineEvent:
    kind: str
    stage: str | None = None
    message: str = ""
    current: float | None = None
    total: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)

class EventSink(Protocol):
    def __call__(self, event: PipelineEvent) -> None: ...

class CancellationToken:
    def cancel(self) -> None: ...
    def is_cancelled(self) -> bool: ...
    def raise_if_cancelled(self) -> None: ...
```

Recognized event kinds:
- `pipeline_started`
- `stage_started`
- `stage_progress`
- `stage_cache_hit`
- `stage_completed`
- `log`
- `pipeline_completed`
- `pipeline_failed`
- `pipeline_cancelled`

Recognized stage names:
- `source`
- `separate`
- `normalize`
- `asr`
- `segment`
- `export`

Unknown event kinds/stages must not crash the GUI; they render as log entries only.

## Stage Progress

Overall progress is based on six stage weights, not elapsed time:

| Stage | Weight |
| --- | ---: |
| Source | 15% |
| Vocal Separation | 25% |
| Normalize | 5% |
| ASR | 35% |
| Segment | 10% |
| Export | 10% |

A cache-hit stage immediately contributes its full weight and is labeled `Cached`.

Fine-grained progress:
- Bilibili/download: bytes downloaded / expected bytes where available.
- Demucs: stage is indeterminate unless Demucs exposes reliable progress; activity log remains live.
- Normalize: indeterminate because FFmpeg is short and currently not instrumented for duration.
- ASR: use segment end timestamp divided by normalized audio duration when available; otherwise indeterminate.
- Segment/export: count completed records when available.

The UI must never fabricate percentages when the core has no trustworthy measurement; show an indeterminate animation instead.

## Resume/Cache UX

V2.3 compact caching remains the only cache policy.

On rerun:
- cached source -> Source row becomes `Cached`.
- cached ASR -> Source/ASR relevant rows become `Cached` when the corresponding cache hit occurs.
- if a successful compacted task needs separation/normalize again because downstream parameters changed, the UI shows those stages as running rather than implying the entire task is new.

No new cache-level setting is added.

## Cancellation

The Stop button performs cooperative cancellation.

- Source downloads check cancellation between chunks/segments.
- Pipeline checks cancellation before and after every stage.
- ASR checks cancellation while consuming Whisper segments.
- Normalize and Demucs use a cancellable process/API wrapper; on cancellation, their active child operation is terminated where possible and the current stage is marked interrupted/failed safely.
- Completed cache stages remain valid; partial outputs use `.part` or stage status and are not marked completed.
- Stop button changes to `Stopping...` and is disabled until worker exits.

Cancellation must never delete valid completed V2.3 cache outputs.

## Demucs Packaging Adaptation

Current V2.3 uses `sys.executable -m demucs`, which is not valid after freezing because `sys.executable` becomes `VoiceDatasetBuilder.exe`.

Refactor `separator.py` behind the same public `separate_vocals(...) -> Path` interface:
- default source/dev execution may still use subprocess when not frozen if convenient;
- frozen execution uses a direct Demucs Python entry/API or an internal callable runner that does not rely on launching `sys.executable -m demucs`;
- output remains `vocals.flac` under the same cache directory structure;
- separator cache signature remains based on model/skip/input, not invocation mechanism.

## FFmpeg Runtime Resolution

Create `tts_builder/runtime.py` with `resolve_binary(name)`:
1. check bundled runtime directory (`sys._MEIPASS`/application directory `bin/`) when frozen;
2. check normal PATH;
3. raise actionable error.

Windows release build copies `ffmpeg.exe` and `ffprobe.exe` into the distribution `bin/` when supplied in `vendor/ffmpeg/`. Development mode may use PATH.

## GUI Components

Create `tts_builder/gui/`:

- `app.py` — QApplication bootstrapping and global application metadata.
- `main_window.py` — window composition and interaction wiring only.
- `styles.py` — QSS theme constants and style sheet.
- `source_input.py` — URL/local path input card with drag/drop.
- `settings_panel.py` — speaker/language/model/output fields.
- `progress_panel.py` — stage rows, overall progress, current status.
- `log_panel.py` — collapsible bounded log view.
- `controller.py` — TaskController and QThread worker, maps PipelineEvent to Qt signals.
- `models.py` — small GUI-only task state/view model dataclasses if needed.

Production Python files should remain approximately <=200 lines where practical; split by responsibility instead of building a monolithic `main_window.py`.

## Input Behavior

The source input accepts exactly one source in GUI V1.

Supported interactions:
- paste URL;
- type/paste local path;
- Browse button;
- drag a local file onto the source card.

Validation before Start:
- source non-empty;
- local source exists if not URL;
- speaker non-empty;
- output path is writable/creatable.

Language choices include Auto, Japanese (`ja`), Chinese (`zh`), English (`en`) with an editable/manual code fallback if straightforward; otherwise V1 exposes the three plus Auto.

ASR model defaults to `large-v3-turbo` and is editable via combo box, but no model download manager is added.

## Task Execution

GUI tasks run in a dedicated `QThread`; the Qt GUI thread never invokes Demucs, FFmpeg, network downloads, or Whisper directly.

Rules:
- only one active task at a time;
- Start inputs are disabled while running;
- Stop enabled while running;
- window close during an active task prompts once to stop and exit;
- completion displays accepted/rejected clip counts and output path;
- failure displays a concise error banner and preserves full details in Activity log.

## CLI Compatibility

`build_dataset.py` continues to work with existing flags.

The CLI may use the same event system internally but must preserve current human-readable output sufficiently for existing tests/users. No GUI dependency may be imported by CLI/core modules; PySide6 is only imported inside `tts_builder.gui` or the GUI launcher.

## Entry Points

- `build_dataset.py` — existing CLI.
- `voice_dataset_builder.py` — GUI development launcher.

Windows release entry point is built from `voice_dataset_builder.py` as `VoiceDatasetBuilder.exe` with no console window.

## Dependencies

Runtime core dependencies remain unchanged plus:
- `PySide6` for GUI.

Build-only dependencies:
- `PyInstaller`.

Keep build dependencies separate from core runtime requirements where practical (`requirements-gui.txt`, `requirements-build.txt`).

## Windows Packaging

Use PyInstaller `onedir`, not `onefile`.

Expected release structure:

```text
VoiceDatasetBuilder/
├── VoiceDatasetBuilder.exe
├── _internal/              # PyInstaller runtime/dependencies
└── bin/
    ├── ffmpeg.exe
    └── ffprobe.exe
```

A PowerShell build script performs:
1. dependency sanity checks;
2. tests;
3. PyInstaller build;
4. copy bundled FFmpeg if available;
5. smoke test the produced executable launch/import path where feasible.

The package can be zipped for distribution. A later installer is out of scope.

## Model Assets and Cache

Whisper and Demucs model weights are NOT embedded into the EXE distribution in V1 because they are large and already use external caches.

The packaged app uses the standard Hugging Face/PyTorch cache locations or user-configured `HF_HOME`/`TORCH_HOME`. On first use, a missing model may download as it does in CLI today. UI status/log should explicitly show model preparation/loading rather than looking frozen.

This keeps the application bundle materially smaller and allows model updates without rebuilding the EXE.

## Error Handling

User-visible errors are concise:
- FFmpeg missing from bundle/PATH;
- model download/load failure;
- source acquisition failure;
- GPU/CUDA failure;
- output permission failure;
- cancellation.

Full exception strings go to Activity log. Core exceptions remain raised so CLI behavior and tests retain visibility.

## Testing Strategy

Core unit tests stay headless.

Add tests for:
- event order and cache-hit events;
- cancellation state behavior;
- CLI works without importing PySide6;
- GUI controller maps core events to Qt signals;
- source input validation and local drag/drop parsing;
- progress weight aggregation;
- runtime bundled/PATH binary resolution;
- separator frozen invocation path with Demucs runner abstraction;
- main window starts with correct defaults and Start disabled until required fields valid;
- worker completion/failure/cancel signal paths.

Set `QT_QPA_PLATFORM=offscreen` for CI/headless widget tests.

## Success Criteria

1. Existing V2.3 CLI tests continue to pass.
2. GUI launches with `python voice_dataset_builder.py` in development.
3. User can paste the Bilibili URL or choose a local file and start a task without opening a terminal.
4. Pipeline stages and cache hits visibly update in the GUI.
5. UI remains responsive during download, Demucs and ASR.
6. Stop leaves completed cache stages reusable.
7. Successful run produces the same `manifest.jsonl`, `dataset.list`, transcripts and clips as CLI for equivalent config.
8. Windows onedir build produces a launchable `VoiceDatasetBuilder.exe` entry point.
9. No Spotify trademark/logo/assets are bundled.

## Approved first-run and model-lifecycle addendum

The GUI must remain a light launch: opening the application performs local environment checks only and must not trigger network access or model downloads.

On the first launch, show one concise welcome/environment card that explains: model downloads require several GB and may take time; NVIDIA CUDA is recommended; CPU mode remains supported but slower; online media/model downloads require networking and resumable cache is preserved; media processing remains local. Detect OS, memory, FFmpeg, storage, and usable NVIDIA/CUDA capability. Recommend `large-v3-turbo` when CUDA is available and `small` for CPU-only systems, while allowing later manual model selection.

Persist only a small app configuration: first-run completion, model root, output root, and preferred ASR model. The selected model root controls internal `HF_HOME=<root>/huggingface` and `TORCH_HOME=<root>/torch`; users never need to manage those variables directly. Changing the model root does not move existing models.

`Build Dataset` starts with a visible Prepare stage. If the selected Whisper model is absent, show estimated download size, model-cache location, and a `Download & Continue` confirmation before downloading. Cached models must be usable without a network check. Network/download failures must be presented as a concise actionable error with technical details available separately; partial Hugging Face/Bilibili cache data is preserved for retry.
