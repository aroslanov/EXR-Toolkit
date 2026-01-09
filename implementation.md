# EXR Channel Recombiner — Implementation Plan (Phase 1)

Date: 2026-01-09

## 1) Goal
Build a runnable Python 3.12 desktop GUI app (Qt 6) that:

- Loads multiple image sequences.
- Inspects **all channels** and **all OpenEXR attributes exposed by OpenImageIO (OIIO)** per file.
- Lets the user construct a new output channel set by selecting channels from any inputs, optionally renaming them.
- Preserves EXR integrity: **no silent metadata loss**, no implicit conversions, and feature parity strictly limited to what OIIO exposes.
- Exports a new OpenEXR image sequence with user-controlled EXR features (compression, attributes, etc.).

Primary function is **general-purpose channel recombination**; Cryptomatte must work because it’s “just channels + metadata” (no special-case code).

## 2) Non-Negotiables / Constraints

- Channel recombination is the primary function.
- Metadata/attributes are first-class: readable, editable, selectable, and never silently changed/dropped.
- Output EXR supports all EXR features that OIIO exposes (and only those; no manual EXR hacking).
- No hard-coded channel semantics (RGB/depth/normals/Cryptomatte are treated identically).
- Validation must block export if requirements are not satisfied.
- Code is modular and future-proof (channel math, bit-depth conversion, OCIO later).

## 3) Technology Choices

- Python: 3.12
- GUI: Qt 6 via **PySide6** (preferred for licensing friendliness); keep a thin abstraction so PyQt6 could be swapped.
- Image I/O: **OpenImageIO Python bindings** (`OpenImageIO` module).
- Output format: OpenEXR written through OIIO.

## 4) Deliverables (Phase 1)

- A runnable GUI app.
- A robust internal model for:
  - Sequences and frame lists
  - Channels and per-channel format/type
  - Attributes/metadata with editable types
  - Output recipe/spec
- Export pipeline that:
  - Implements mismatch policies
  - Recombines channels without implicit conversions
  - Writes EXR with selected attributes and user-selected EXR-specific options exposed by OIIO
- Logging + progress.

## 5) UX Requirements Mapping

### Input Panel
- Load/close sequence
- Sequence selector
- Channel list
- Channel properties viewer
- Metadata viewer/editor (structured)

### Output Panel
- Output channel list
- Editable output channel names
- Source reference per channel (seq/channel)

### Export Panel
- Output path + filename pattern
- Compression selector
- EXR feature editor (attributes exposed by OIIO)
- Export button + progress
- Detailed log window

## 6) Core Concepts & Data Model (No Loose Dicts)

Use `@dataclass` and typed enums. Avoid “free-form dicts” except at the boundary with OIIO APIs.

### 6.1 Types

- `FrameIndex`: `int` (the actual frame number from the sequence).
- `ChannelName`: `str` (stored as-is; no parsing assumptions).
- `PartName`: `str | None` (for multi-part support if OIIO exposes it).

### 6.2 Attribute Model

OIIO exposes attributes via `ImageSpec` (and potentially per-subimage/part spec). We model them as structured objects.

- `AttributeType` (enum-ish):
  - scalar: int, float, string
  - vector/array: int[], float[], string[]
  - matrix: float[9]/float[16] if OIIO reports them that way
  - unknown/raw: fallback to string representation with a “read-only” or “opaque” policy

- `AttributeSpec`:
  - `name: str` (including namespaces like `cryptomatte/...`)
  - `oiio_type: str` (or `OpenImageIO.TypeDesc` stringified)
  - `value: Any` (type-consistent with `oiio_type`)
  - `source: AttributeSource` (enum: `INPUT_SEQ`, `OUTPUT_OVERRIDE`, etc.)
  - `editable: bool` (false if we cannot safely round-trip)

- `AttributeSet`:
  - list of `AttributeSpec`
  - indexing helpers by name
  - stable ordering
  - diff/merge operations that are explicit and logged

### 6.3 Channel Model

- `ChannelFormat`:
  - wraps OIIO’s channel type information (e.g., half/float/uint) as reported in the spec.

- `ChannelSpec`:
  - `name: str`
  - `format: ChannelFormat` (per-channel type)
  - `subimage_index: int` / `part: PartName` (depending on OIIO support)
  - `source: ChannelSourceRef`

- `ChannelSourceRef`:
  - `sequence_id: str`
  - `channel_name: str`
  - `subimage_index: int` (default 0)

### 6.4 Sequence Model

- `SequencePathPattern`:
  - supports printf-style (`%04d`) and hash-style (`####`) patterns.

- `SequenceSpec`:
  - `id: str`
  - `display_name: str`
  - `pattern: SequencePathPattern`
  - `frames: list[int]` (discovered)
  - `static_probe: FileProbe` (channels+attributes from representative frame)
  - `per_frame_probe: dict[int, FileProbe]` (lazy; only if user requests deeper inspection)

- `FileProbe`:
  - `path: str`
  - `subimages: list[SubImageProbe]`

- `SubImageProbe`:
  - `spec: ImageSpecSnapshot`
  - `channels: list[ChannelSpec]`
  - `attributes: AttributeSet`

- `ImageSpecSnapshot`:
  - minimal immutable representation of OIIO `ImageSpec` fields we need:
    - width/height
    - nchannels
    - channelnames
    - channelformats
    - tile sizes (if present)
    - format (pixel format)
    - any other OIIO-exposed fields that matter

### 6.5 Output Recipe Model

- `FrameRangePolicy` (enum):
  - `STOP_AT_SHORTEST`
  - `HOLD_LAST`
  - `PROCESS_AVAILABLE`

- `ExportSpec`:
  - `output_dir: str`
  - `filename_pattern: str` (e.g. `beauty.%04d.exr`)
  - `frame_policy: FrameRangePolicy`
  - `compression: str` (mapped to OIIO EXR compression attribute)
  - `output_attributes: AttributeSet` (final attributes to write)
  - `output_channels: list[OutputChannel]`
  - `subimage_strategy`: phase-1 default single-part/subimage; extend later

- `OutputChannel`:
  - `output_name: str`
  - `source: ChannelSourceRef`
  - `override_format: ChannelFormat | None` (phase-1: None by default; no implicit conversions)

## 7) OpenImageIO Integration Plan

### 7.1 Reading

- Use `OpenImageIO.ImageInput.open(path)`.
- Enumerate subimages/parts if available:
  - iterate `subimage=0..` using `seek_subimage(subimage, miplevel=0)`.
  - capture `spec = inp.spec()`.
- Extract:
  - `spec.channelnames`
  - `spec.channelformats` (if empty, fall back to `spec.format` semantics — but do not assume; store what OIIO provides)
  - all `spec.extra_attribs` (or `spec.getattribute` enumeration depending on binding)

Important: Different OIIO versions expose attributes differently; implement an adapter layer `OiioSpecAdapter` to normalize.

### 7.2 Writing

- Create output `ImageSpec` with:
  - correct resolution (must match chosen source(s) — phase-1 requires consistent resolution; future may add resampling/cropping non-goal)
  - `channelnames` exactly as user defines
  - `channelformats` or `format` consistent with selected sources

- Set attributes:
  - Apply `ExportSpec.output_attributes` to the `ImageSpec` using OIIO setter APIs.
  - Apply compression and other EXR options via attributes (e.g., `compression`, `lineOrder`, `tile:width`, etc.) **only if OIIO exposes them**.

- Write pixels:
  - For each frame, read needed channels from each source input and assemble into output buffer.
  - Avoid implicit conversion:
    - If source channel format differs from destination channel format and user did not override explicitly, validation fails.

### 7.3 Buffer Assembly Without Assumptions

OIIO can read by channel range; however “arbitrary channel picks across multiple inputs” implies we may read full pixel buffers then slice.

Phase-1 approach (simple, correct):
- For each unique source file used in the output frame:
  - Read all channels (or at least the minimal subset required) into a NumPy array with a dtype matching source.
  - Extract selected channels by index and copy into output buffers.

If NumPy dependency is unwanted, use OIIO’s `ImageBuf` (preferred). Plan:
- Use `OpenImageIO.ImageBuf(path)` and `ImageBufAlgo.channels()` where possible.
- But channels across multiple buffers will still require manual stacking.

Decision for Phase-1:
- Prefer **ImageBuf** for correctness and OIIO-native typing; only use NumPy if OIIO API is too restrictive.
- Add a small `PixelStore` abstraction to hide whether storage is OIIO-native or NumPy.

## 8) Sequence Handling

### 8.1 Pattern Parsing

Support common patterns:
- `foo.%04d.exr`
- `foo.####.exr`

Implement `SequencePathPattern` with:
- `to_regex()` to discover frames
- `format(frame)` to build path

### 8.2 Frame Discovery

- Scan directory for matching filenames.
- Extract frame numbers.
- Sort numeric frames.

### 8.3 Mismatch Policy

If sequences differ in frame lists:
- On export, compute the union/intersection depending on policy:
  - `STOP_AT_SHORTEST`: align by sorted frames; stop when any sequence runs out (by index alignment).
  - `HOLD_LAST`: when a sequence runs out, reuse its last available frame.
  - `PROCESS_AVAILABLE`: for each output frame (from master list), process if all required sources for that frame exist; else skip and log.

Important: Alignment definition must be explicit in UI:
- “By frame number” (preferred) vs “by index”.

Phase-1: Align **by frame number** if frame numbers are discoverable; otherwise fallback to by-index with a warning.

## 9) Metadata / Attribute Handling (Critical)

### 9.1 Principles

- The tool never silently drops metadata.
- Any merge between inputs must be explicit and user-controlled.
- Attribute edits must preserve type and name; invalid edits are blocked.

### 9.2 Attribute UI Model

Expose a generic table editor:
- Columns: Name, Type, Value, Source, Enabled
- Enable/disable per output attribute.
- Provide “import attributes from input sequence X (frame N)” operation that copies attribute set into output.

### 9.3 Attribute Conflicts

If multiple inputs have the same attribute name but different values:
- Do not auto-merge.
- Present conflict resolution:
  - choose source A/B
  - or “custom override”

### 9.4 Cryptomatte Compatibility Without Special Logic

Cryptomatte is validated by:
- Preserving all `cryptomatte/*` attributes exactly as they were when selected.
- Preserving channel names and formats.

No extra parsing or generation is required in phase-1.

## 10) Validation (Must Block Export)

Implement a dedicated validation module returning structured issues.

- `ValidationIssue`:
  - `severity: ERROR|WARNING`
  - `code: str`
  - `message: str`
  - `context: dict`

Validation rules (Phase-1):

1) Output channels
- At least one output channel.
- Output channel names are unique.
- Every output channel has a valid source reference.

2) Channel format / compatibility
- All output channels share same width/height (unless future resampling; for now, error).
- For each output channel, source channel exists at export time.
- Channel type matches (or explicit override is provided) — no implicit conversions.

3) Sequence policy
- Frame-range mismatch policy selected.
- Frame alignment mode (by frame number vs by index) is resolved.

4) Attributes
- Output attributes are type-valid for OIIO.
- If an attribute is known by OIIO to be required for a feature (rare), ensure it is present.
- Any user-edited attribute must round-trip via OIIO setter.

5) Export path
- Output directory exists or can be created.
- Filename pattern includes frame token.

Export button is disabled when there are `ERROR`s.

## 11) Qt 6 UI Architecture

### 11.1 Main Layout

- `MainWindow`
  - Left: Input panel (sequence management + inspection)
  - Center: Output channel builder
  - Right/Bottom: Export settings + log

### 11.2 Model/View

Use Qt’s model/view patterns so UI stays scalable.

Models:
- `SequenceListModel`
- `ChannelListModel` (for selected sequence)
- `AttributeTableModel` (for selected file/subimage)
- `OutputChannelListModel`
- `OutputAttributeTableModel`

Views:
- `QListView`/`QTableView` with delegates for type-aware editing.

### 11.3 Editing Widgets

- Attribute editor:
  - Type-aware editor widgets (spinbox, double, checkbox, line edit)
  - For arrays: a compact JSON-like editor or a separate dialog

- Output channel mapping:
  - Drag/drop from input channel list to output channel list (nice-to-have)
  - Or “Add to output” button
  - Rename inline

### 11.4 Logging

- A central `Logger` service writing to:
  - Qt log pane
  - optional file log

### 11.5 Progress

- Export runs in a worker thread (`QThread`/`QRunnable`) with signals:
  - progress percent
  - current frame
  - messages

## 12) Proposed Project Structure

Phase-1 moves beyond a single file.

- `app/`
  - `main.py` (entry point)
  - `ui/`
    - `main_window.py`
    - `widgets/` (input panel, output panel, export panel)
    - `models/` (Qt models)
  - `core/`
    - `types.py` (dataclasses/enums)
    - `sequence.py` (pattern discovery)
    - `validation.py`
    - `logging.py`
  - `oiio/`
    - `adapter.py` (version-safe spec/attrib enumeration)
    - `reader.py`
    - `writer.py`
    - `recombine.py` (frame assembly)
  - `services/`
    - `project_state.py` (in-memory state)
    - `export_runner.py` (threaded export)

Keep the existing `exr_tool.py` as a temporary scratch or migrate it into `app/main.py`.

## 13) Export Algorithm (Phase-1)

For each output frame in the resolved frame list:

1) Resolve for each output channel: which input file path supplies it (consider mismatch policy).
2) Group channels by source path to minimize reads.
3) For each source path:
   - open via OIIO, read needed channels (or full image if minimal-read is too complex initially).
4) Build output pixel buffer with channels in output order.
5) Build output `ImageSpec`:
   - set channel names
   - set per-channel formats
   - set EXR attributes per `ExportSpec.output_attributes`
6) Write the output EXR.
7) Emit progress + log.

## 14) Phase Plan / Milestones

### Milestone A — Repo Setup & Dependencies
- Ensure `.venv` is used for every run.
- Add `requirements.txt` (or `pyproject.toml`) with:
  - PySide6
  - OpenImageIO
  - (Optional) numpy

### Milestone B — Core Models + Sequence Discovery
- Implement dataclasses/enums.
- Implement sequence pattern discovery.
- Implement a “probe one frame” read.

### Milestone C — OIIO Adapter
- Implement robust attribute enumeration and type mapping.
- Snapshot `ImageSpec` to internal model.

### Milestone D — GUI Skeleton
- Main window layout + empty models.
- Sequence load/unload.
- Channel/attribute inspection.

### Milestone E — Output Builder
- Add channels to output mapping.
- Rename + conflict validation.

### Milestone F — Attribute Editor
- Output attribute set selection + edit.
- Conflict resolution UX.

### Milestone G — Export Runner
- Validation gates.
- Worker thread export.
- Progress + logs.

### Milestone H — Verification
- Manual validation on:
  - RGB beauty
  - utility AOVs
  - depth/normal
  - Cryptomatte sample (ensuring metadata preserved)

## 15) Testing Strategy (Lightweight)

No heavy test suite required, but add targeted tests if feasible:

- Unit tests for:
  - sequence pattern parsing
  - frame list alignment policies
  - attribute type parsing/round-tripping logic
  - validation rules

Integration/manual:
- Export a small 2–5 frame set and open in:
  - `oiiotool --info -v`
  - Nuke/Houdini (user-side)

## 16) Operational Notes (Important)

- Always activate the venv before running:
  - PowerShell: `.\.venv\Scripts\Activate.ps1`

- Avoid reliance on features not exposed by OIIO.
- If OIIO cannot enumerate/set an attribute type safely, mark it read-only and preserve it by copying from a chosen input spec where possible.

## 17) Open Questions (To Resolve During Implementation)

These depend on OIIO Python binding capabilities in the installed version:

- Exact API to enumerate all attributes reliably (`extra_attribs`, `attribs`, `getattribute`, etc.).
- Multi-part support exposure:
  - Are EXR parts represented as subimages in OIIO Python? If yes, map parts to subimages.
- Per-channel formats access:
  - Does `spec.channelformats` always populate? If not, how does OIIO represent per-channel types?
- Tile/lineorder exposure:
  - Which attributes should be surfaced as standard UI controls vs generic attribute editor only?

We will answer these by probing the installed OIIO build and adjusting the adapter.
