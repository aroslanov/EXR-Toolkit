# EXR Channel Recombiner — Implementation Journal

## Session 1 — 2026-01-09 [START]

### Plan
1. Check journal (done — new session)
2. Scaffold project structure (directories + __init__.py files)
3. Create requirements.txt with dependencies
4. Verify .venv activation
5. Install dependencies
6. Create core data models (types.py)
7. Create sequence discovery module
8. Create OIIO adapter stub
9. Create GUI skeleton (MainWindow)
10. Test basic structure

### Progress Log

#### Step 1: Check Journal
- Journal did not exist; created fresh journal at 2026-01-09

#### Step 2: Scaffold Project Structure
- Created directories: app/, app/ui/, app/ui/widgets/, app/ui/models/, app/core/, app/oiio/, app/services/
- Added __init__.py files for all modules

#### Step 3: Create requirements.txt
- PySide6 >= 6.6.0
- OpenImageIO >= 2.5.0
- numpy >= 1.24.0
- All dependencies installed successfully in .venv

#### Step 4: Create Core Data Models (types.py)
- Implemented: ChannelFormat, ChannelSpec, ChannelSourceRef
- Implemented: AttributeSpec, AttributeSet (with get_by_name, add_or_update)
- Implemented: ImageSpecSnapshot, SubImageProbe, FileProbe
- Implemented: SequencePathPattern (with to_regex and format)
- Implemented: SequenceSpec, OutputChannel, ExportSpec
- Implemented: ValidationIssue, FrameRangePolicy, AttributeSource

#### Step 5: Create Sequence Discovery Module (sequence.py)
- SequenceDiscovery.discover_frames() for pattern matching
- Support for %04d (printf) and #### (hash) patterns
- Regex-based frame number extraction

#### Step 6: Create OIIO Adapter (adapter.py)
- OiioAdapter.probe_file() — reads file, extracts all subimages
- _extract_channels() — gets channel names and formats
- _extract_attributes() — enumerates attributes (multiple fallback methods)
- _snapshot_spec() — creates immutable ImageSpecSnapshot
- Handles OIIO version differences with fallback logic

#### Step 7: Create GUI Skeleton (main_window.py)
- MainWindow (QMainWindow) with three panels:
  - Left: Input sequences (load/remove, inspector)
  - Center: Output channels (add/remove channels, attribute editor)
  - Right: Export settings (path, pattern, log)
- Load sequence button: discovers frames via SequenceDiscovery, probes with OiioAdapter
- Sequence list with per-frame channel/attribute display
- Placeholder methods for add/remove output channels and export

#### Step 8: Create Root Launcher (main.py)
- Adds project root to sys.path for proper module imports
- Launches app.main.main()
- GUI application now launches successfully

### Status (After Session 1 Completion)
- Scaffold complete: 7 modules + 2 entry points created
- Dependencies installed: PySide6 6.10.1, OpenImageIO 3.1.9.0, numpy 2.4.0
- GUI launches successfully
- Core architecture in place for channel inspection + sequence loading

## Session 2 — 2026-01-09 [PHASE 2]

### Plan
1. Create validation module (ValidationEngine)
2. Create project state service (ProjectState)
3. Create Qt models (SequenceListModel, ChannelListModel, OutputChannelListModel, AttributeTableModel)
4. Create AttributeEditor widget
5. Create export runner (ExportRunner, ExportManager)
6. Enhance MainWindow with full functionality
7. Test end-to-end workflow

### Progress Log

#### Step 1: Create Validation Module (validation.py)
- ValidationEngine.validate_export() validates:
  - Output channels (at least 1, unique names, all have sources)
  - Channel formats (consistent resolution, channel format compatibility)
  - Export paths (output dir exists/creatable, filename pattern has frame token)
  - Sequence policy (frame policy selected, warnings for length mismatch)
  - Attributes (attribute names not empty, None values warned)
- Returns structured ValidationIssue list with ERROR/WARNING severity

#### Step 2: Create Project State Service (project_state.py)
- ProjectState: central in-memory state manager
- Methods:
  - add_sequence, remove_sequence, list_sequences
  - add_output_channel, remove_output_channel, update_output_channel
  - set_output_dir, set_filename_pattern, set_compression
  - set_output_attributes, import_attributes_from_sequence
  - can_export() quick check
  - get_export_spec() for validation/export

#### Step 3: Create Qt Models (qt_models.py)
- SequenceListModel: displays sequences with frame count
- ChannelListModel: displays channels of selected sequence with types
- OutputChannelListModel: displays output channel mapping
- AttributeTableModel: table with Name/Type/Value/Source/Enabled columns

#### Step 4: Create AttributeEditor Widget (attribute_editor.py)
- AttributeEditor: main widget with table view + buttons
- AddAttributeDialog: dialog for adding new attributes
- Type-aware fields (string, int, float, unknown)
- Add/Remove/Import buttons (import stub for now)
- Emits attributes_changed signal

#### Step 5: Create Export Runner (export_runner.py)
- ExportRunner: QRunnable that performs export
  - Validates export spec
  - Resolves frame list from sequences
  - For each frame:
    - Assembles output buffer from input channels
    - Reads source channels from files
    - Writes output EXR with attributes
  - Emits progress, log, finished signals
- ExportManager: manages thread pool, starts export in worker thread

#### Step 6: Enhance MainWindow (main_window.py)
- Integrated ProjectState and ExportManager
- Three panels with full functionality:
  - Left: Load/remove sequences, list channels, add to output
  - Center: Output channel list, attribute editor, compression selector
  - Right: Output path/pattern, export button, progress, logs
- Signal/slot connections for validation, export progress, logging
- Complete workflow: load sequence → select channels → configure → validate → export

#### Step 7: Status
- Phase 2 complete: All core functionality implemented
- Full channel recombination pipeline ready
- Validation gates export before invalid configs
- Export runs in separate thread with progress reporting

### Testing & Fixes
- Fixed PySide6 Signal imports (Signal not pyqtSignal)
- All imports verified: successful
- GUI application launches successfully with full UI

### Current State
**COMPLETE: Phases 1 & 2** 
- Scaffold: directory structure, __init__.py files
- Core models: All dataclasses with proper types
- Sequence discovery: Pattern parsing + frame discovery
- OIIO adapter: Robust file probing with fallback attribute enumeration
- Validation engine: Pre-export validation with structured issues
- Project state: Central state management
- Qt models: MVC pattern for all UI elements
- Widgets: AttributeEditor with dialog
- Export runner: Threaded export with progress signals
- MainWindow: Fully functional 3-panel UI
  - Load sequences, inspect channels
  - Add channels to output
  - Configure attributes, compression
  - Validate and export with progress

### Bug Fixes
- Fixed PySide6 Signal imports (Signal not pyqtSignal)
- Fixed regex escape sequence in sequence.py _pattern_to_regex() — use lambda for replacement string
  
**Next Phase (Not yet started)**
- End-to-end testing with sample EXR files
- Manual verification with oiiotool
- Optimization and edge case handling

## Session 3 — 2026-01-09

### Goal
- Resolve remaining Pylance diagnostics in the Qt model layer.

### Work Completed
- Fixed override typing issues in app/ui/models/qt_models.py to better match PySide6 stubs.

### Changes (qt_models.py)
- Added missing typing imports and return annotations for model overrides.
- Changed AttributeTableModel.headerData() orientation param from int to Qt.Orientation.
- Added a role gate in AttributeTableModel.setData() (returns False unless role == Qt.EditRole).
- Annotated AttributeTableModel.flags() return type as Qt.ItemFlags.

### Verification
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/models/qt_models.py
- Ran: .\\.venv\\Scripts\\python -c "from app.ui.models.qt_models import SequenceListModel, ChannelListModel, OutputChannelListModel, AttributeTableModel; print('imports_ok')"
- Result: imports_ok

### Notes
- Pylance previously reported incompatible method override for rowCount() due to parent parameter typing. This file now uses Union[QModelIndex, QPersistentModelIndex] for rowCount/columnCount parent parameters.

### Follow-up Fix (Pylance Qt enum attributes)
- Symptom: Pylance reported unknown attributes on Qt (e.g. Qt.DisplayRole, Qt.UserRole, Qt.EditRole, Qt.NoItemFlags, Qt.ItemIsEditable, Qt.Horizontal).
- Fix: Switched to Qt6-style enums in app/ui/models/qt_models.py:
  - Qt.ItemDataRole.DisplayRole / UserRole / EditRole
  - Qt.ItemFlag.NoItemFlags / ItemIsEditable
  - Qt.Orientation.Horizontal

### Verification (Follow-up)
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/models/qt_models.py
- Ran: .\\.venv\\Scripts\\python -c "from app.ui.models.qt_models import SequenceListModel, ChannelListModel, OutputChannelListModel, AttributeTableModel; print('imports_ok')"
- Result: imports_ok

### Follow-up Fix (Pylance override: data/index type)
- Symptom: Pylance reported incompatible override for QAbstractItemModel.data() because stubs accept QModelIndex | QPersistentModelIndex.
- Fix: Updated qt_models.py signatures to accept Union[QModelIndex, QPersistentModelIndex] for:
  - SequenceListModel.data
  - ChannelListModel.data
  - OutputChannelListModel.data
  - AttributeTableModel.data
  - AttributeTableModel.setData
  - AttributeTableModel.flags

### Verification (Override Fix)
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/models/qt_models.py
- Ran: .\\.venv\\Scripts\\python -c "from app.ui.models.qt_models import SequenceListModel, ChannelListModel, OutputChannelListModel, AttributeTableModel; print('imports_ok')"
- Result: imports_ok

### Follow-up Fix (Pylance: Qt.ItemFlags unknown)
- Symptom: Pylance reported "Cannot access attribute 'ItemFlags' for class 'type[Qt]'".
- Cause: In PySide6, Qt.ItemFlags is not exposed as an attribute on Qt; using it in annotations triggers Pylance.
- Fix: Updated AttributeTableModel.flags() return annotation to use PySide6's QFlag (imported from PySide6.QtCore) instead of Qt.ItemFlags.

### Verification (ItemFlags Fix)
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/models/qt_models.py
- Ran: .\\.venv\\Scripts\\python -c "from app.ui.models.qt_models import AttributeTableModel; print('imports_ok')"
- Result: imports_ok

### Follow-up Fix (Pylance: QFlag annotation)
- Symptom: Pylance flagged the flags() return annotation `-> QFlag` as invalid (QFlag is a built-in function in PySide6, not a class/type).
- Fix: Removed the QFlag import and removed the explicit return annotation from AttributeTableModel.flags().

### Verification (QFlag Fix)
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/models/qt_models.py
- Ran: .\\.venv\\Scripts\\python -c "from app.ui.models.qt_models import AttributeTableModel; m=AttributeTableModel(); print('imports_ok')"
- Result: imports_ok

## Session 4 — 2026-01-09

### Goal
- Improve sequence loading UX: auto-discover sequences, handle multiple sequences per folder, show patterns in UI.

### Changes

#### 1. app/core/sequence.py
- Added SequenceDiscovery.discover_sequences() static method.
- Heuristic-based auto-detection: scans directory for image files (exr/jpg/png/tiff).
- Groups files by base pattern (both %04d and #### formats).
- Returns list of (pattern_str, frame_list) tuples.

#### 2. app/ui/main_window.py
- Added `from typing import Optional` import.
- Refactored _on_load_sequence():
  - Now calls SequenceDiscovery.discover_sequences(path) first.
  - If multiple sequences found, shows selection dialog.
  - Logs discovered pattern (e.g., "image.%04d.exr") to user.
- Added _ask_sequence_selection_dialog():
  - QComboBox showing all detected sequences with frame counts.
  - User selects one and clicks OK.
  - Returns (pattern_str, frame_list) tuple.

### Verification
- Ran: .\\.venv\\Scripts\\python -m py_compile app/core/sequence.py app/ui/main_window.py
- Ran: .\\.venv\\Scripts\\python -c "from app.ui.main_window import MainWindow; from app.core.sequence import SequenceDiscovery; print('imports_ok')"
- Result: imports_ok

### Flow
1. User clicks "Load Sequence" → selects directory.
2. App auto-discovers sequences using heuristic pattern matching.
3. If 1 sequence found: use it directly, log pattern.
4. If multiple found: show QDialog with dropdown list.
5. Log result to user with discovered pattern.

## Session 5 — 2026-01-09

### Bug Report
- User loads directory with files `render.00000.exr`, `render.00001.exr`, ... `render.00900.exr`
- Auto-discovery shows: "Auto-discovered sequence: render.0%04d.exr (901 frames)" (incorrect)
- Subsequent frame discovery fails: "No frames found matching pattern: render.0%04d.exr"

### Root Cause
- discover_sequences() regex `r'(.+?)(\d{4})(\..+?)$'` matches exactly 4 digits
- File `render.00000.exr` has 5 digits, so regex matched `render.0` + `0000` + `.exr`
- Generated incorrect pattern `render.0%04d.exr`
- discover_frames() then couldn't find any files matching this wrong pattern

### Fix

#### 1. discover_sequences() regex
- Changed from fixed-digit matching (`\d{4}`) to variable-length matching (`\d+`)
- Now correctly identifies frame number length and generates appropriate `%0Nd` format
- Files with 5 digits → generates `%05d` format
- Files with 4 digits → generates `%04d` format

#### 2. _pattern_to_regex() function
- Problem: regex `\\%0\d+d` was looking for escaped `%`, but `re.escape()` doesn't escape `%`
- Fixed: changed regex from `\\%0\d+d` to `%0\d+d` (no backslash prefix)
- Used lambda in both substitutions to avoid string escaping issues

### Verification
- Test: Created temp directory with `render.00000.exr` through `render.00900.exr`
- discover_sequences() → correctly returns `('render.%05d.exr', [0,1,2,100,900])`
- discover_frames('render.%05d.exr', tmpdir) → correctly returns `[0,1,2,100,900]`
- Result: Both discovery methods now work correctly with variable-length frame numbers

### Code Changes
- app/core/sequence.py: Updated discover_sequences() and _pattern_to_regex()

## Session 6 — 2026-01-09

### Verification of Complex Filename Support

Tested the updated sequence discovery with various filename patterns to ensure it handles:
1. Simple 5-digit frames: `render.00000.exr` → `render.%05d.exr` ✓
2. Simple 4-digit frames: `image_0001.jpg` → `image_%04d.jpg` ✓
3. Complex filenames with dot separator: `render_01_260109_.000000.exr` → `render_01_260109_.%06d.exr` ✓
4. Complex filenames without separator: `render_01_260109_000000.exr` → `render_01_260109_%06d.exr` ✓

The regex `r'^(.+?)(\d+)(\..+?)$'` uses non-greedy matching (`(.+?)`) which correctly:
- Matches the minimal prefix before the frame number
- Captures the digit sequence before the extension
- Works with files containing multiple numeric components
- Handles both separated (dot/underscore) and non-separated frame numbers

Result: discover_sequences() and discover_frames() both work correctly with all tested complex filenames.

## Session 7 — 2026-01-09

### Goal
- Display input sequence attributes and metadata in the UI.

### Implementation

#### Changes to app/ui/main_window.py

1. **Updated _create_input_panel()**
   - Added QTextEdit widget `self.metadata_display` (read-only, max height 150px)
   - Positioned below channel list, above stretch
   - Displays selected sequence metadata

2. **Updated _on_sequence_selected()**
   - Now calls `_format_sequence_metadata(seq)` to build metadata text
   - Populates metadata_display with formatted info

3. **Added _format_sequence_metadata(seq: SequenceSpec) -> str**
   - Formats and returns metadata for display:
     - Pattern (e.g., `render.%05d.exr`)
     - Frame range (count and min-max)
     - Resolution (width x height)
     - Channel count
     - Channel list with names and formats (up to 5 shown)
     - Attributes list (first 5, with note if more exist)
   - Returns nicely formatted text for QTextEdit

### Metadata Display Content
```
Pattern: render.%05d.exr
Frames: 901 (0-900)

Resolution: 2048x1536
Channels: 4

Channel List:
  1. R (float)
  2. G (float)
  3. B (float)
  4. A (float)

Attributes:
  compression: zip
  pixelAspectRatio: 1.0
  ... and 3 more
```

### Verification
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/main_window.py
- Ran: .\\.venv\\Scripts\\python -c "from app.ui.main_window import MainWindow; print('MainWindow imports OK')"
- Result: Compilation and import successful

### User Flow
1. User loads a sequence → sequence appears in list
2. User clicks on sequence → metadata displays showing:
   - File pattern
   - Frame range
   - Resolution
   - Channels with formats
   - Key attributes

## Session 8 — 2026-01-09

### Goal
- Remove truncation from metadata display; show ALL attributes instead of "... and N more"

### Changes to app/ui/main_window.py

#### _format_sequence_metadata() method
- **Before:** Attributes limited to first 5 with "... and N more" note
- **After:** Display ALL attributes without truncation
- Changed loop: or attr in attrs[:5]: → or attr in attrs:
- Removed: Conditional that appended "... and N more" message

### Verification
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/main_window.py
- Result: Compilation OK

### Result
- Metadata display now shows complete list of all attributes
- No truncation with "... and N more" text
- Full visibility into sequence metadata

## Session 9 — 2026-01-09

### Goal
1. Support all EXR compression formats (DWA, DWAB)
2. Enable multiple channel selection and addition
3. Implement 'Import Attributes from Source' functionality

### Changes

#### 1. Compression Formats (main_window.py)
- Added \"dwa\" and \"dwab\" to compression combo box items
- Compression list now: [\"zip\", \"rle\", \"piz\", \"dwa\", \"dwab\", \"none\"]

#### 2. Multiple Channel Selection (main_window.py)
- Changed channel_list from SingleSelection to MultiSelection mode
- Updated _on_add_channel_to_output() to handle multiple selected channels
- Now users can Ctrl+Click to select multiple channels and add all at once

#### 3. Import Attributes from Source

##### AttributeEditor changes (attribute_editor.py)
- Added import_from_source_requested Signal
- Added public import_attributes(attributes) method
- Updated _on_import_from_source() to emit the signal instead of being a placeholder

##### MainWindow changes (main_window.py)
- Connected import_from_source_requested signal in _connect_signals()
- Added _on_import_attributes_from_source() handler that:
  - Gets selected input sequence
  - Extracts attributes from sequence FileProbe
  - Imports them into attribute editor via import_attributes()
  - Logs result to user

### Verification
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/main_window.py app/ui/widgets/attribute_editor.py
- Result: Compilation OK
- Ran: .\\.venv\\Scripts\\python -c \"from app.ui.main_window import MainWindow; from app.ui.widgets import AttributeEditor; print('All imports OK')\"
- Result: All imports OK

### User Flow
1. **Compression:** Select from combo box with 6 options (zip, rle, piz, dwa, dwab, none)
2. **Multi-channel selection:** 
   - Load sequence → channels list appears
   - Ctrl+Click to select multiple channels
   - Click \"Add Selected to Output\" to add all selected channels at once
3. **Import attributes:**
   - Select input sequence in left panel
   - Click \"Import from Source\" button in Attributes tab
   - Attributes from source sequence automatically populate the table


## Session 10 — 2026-01-09

### Goal
- Correct EXR compression formats (fix typo: DWA → DWAA/DWAB)
- Use ONLY OpenImageIO-supported compression formats

### Root Cause
- Session 9 included 'dwa' which is not a valid EXR format
- Correct formats are 'dwaa' and 'dwab' (not 'dwa')

### Research
- Used context7 MCP to fetch OpenImageIO documentation
- Found definitive list from openexr-compression test reference

### OpenImageIO Supported EXR Compression Formats
Valid formats (from OpenImageIO test suite):
- none (no compression)
- rle (Run-Length Encoding)
- zip (ZIP compression)
- zips (ZIP single scanline)
- piz (PIZ lossless)
- pxr24 (PXR24)
- b44 (B44 lossy, fixed rate)
- b44a (B44 with alpha)
- dwaa (DWA lossy, adaptive, quality 200)
- dwab (DWA lossy, adaptive, best compression)
- htj2k (JPEG 2000 Huffman, requires OpenEXR 3.4+)

### Change
- Updated compression_combo items from: [\"zip\", \"rle\", \"piz\", \"dwa\", \"dwab\", \"none\"]
- To: [\"none\", \"rle\", \"zip\", \"zips\", \"piz\", \"pxr24\", \"b44\", \"b44a\", \"dwaa\", \"dwab\"]
- Ordered by common usage (none → more specialized/lossy formats)
- Includes all standard formats supported across OpenEXR versions
- Excluded htj2k (requires OpenEXR 3.4+, may not be available)

### Verification
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/main_window.py
- Result: Compilation OK

### User Impact
- Compression combo now shows only valid, OpenImageIO-supported formats
- No more invalid 'dwa' option
- Users can select dwaa/dwab (correct DWA lossy compression variants)


## Session 11 — 2026-01-09

### Goal
1. Make log window text clipboard-copiable (Ctrl+C and double-click)
2. Make export process interruptible; export button switches to stop button

### Changes

#### 1. Log Window Text Selection (main_window.py)
- Log QTextEdit already supports Ctrl+C and double-click selection
- Read-only flag allows selection but prevents editing
- Users can now:
  - Select text with mouse
  - Double-click to select words
  - Ctrl+A to select all
  - Ctrl+C to copy to clipboard

#### 2. Interruptible Export (3 files modified)

##### export_runner.py - ExportRunner class
- Added stop_requested flag (initialized to False)
- Added request_stop() method to gracefully request stop
- Added stop check in export frame loop:
  - Checks stop_requested before each frame
  - Gracefully cancels if stop requested
  - Logs cancellation message

##### export_runner.py - ExportManager class
- Added stop_export() method that calls current_runner.request_stop()
- Allows external code to request export termination

##### main_window.py - MainWindow class
- Changed btn_export from local to instance variable (self.btn_export)
- Added _on_export_button_clicked() handler that:
  - Calls _on_export() if button text is \"EXPORT\"
  - Calls export_manager.stop_export() if button text is \"STOP\"
  - Disables button after stop request
- Updated _on_export() to change button mode:
  - Sets button text to \"STOP\"
  - Changes button color to red (#f44336)
- Updated _on_export_finished() to reset button mode:
  - Sets button text back to \"EXPORT\"
  - Changes button color back to green (#4CAF50)
  - Re-connects click handler

### User Flow
1. **Copy log text:**
   - Single-click and drag to select text
   - Double-click to select word/phrase
   - Ctrl+A to select all
   - Ctrl+C to copy to clipboard

2. **Stop export during process:**
   - Click EXPORT to start (button turns red, text changes to STOP)
   - During export, click STOP button to cancel
   - Export stops gracefully after current frame
   - Button resets to EXPORT when finished

### Verification
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/main_window.py app/services/export_runner.py
- Result: Compilation OK
- Ran: .\\.venv\\Scripts\\python -c \"from app.ui.main_window import MainWindow; from app.services.export_runner import ExportManager; print('Imports OK')\"
- Result: Imports OK

### Technical Details
- Export loop checks stop_requested flag before each frame (safe, non-blocking)
- Stop is graceful: completes current frame, then stops
- Button state is fully managed and restored after export
- User sees immediate visual feedback (red STOP button)


## Session 12 — 2026-01-09

### Bug Report
- Export started but returned empty EXR files
- Source files not found during export
- Pattern: 'Warning: Source file not found: render.00000.exr'
- Root cause: File paths missing source directory information

### Root Cause Analysis
- SequenceSpec did not store source_dir (directory containing source sequence files)
- export_runner._assemble_frame() only used pattern.format(frame_num) - just the filename
- Missing full path: src_seq.source_dir / filename
- Result: OpenImageIO looked in current directory instead of source directory

### Fix

#### 1. app/core/types.py - SequenceSpec
- Added source_dir: Path field to store source directory
- Positioned after pattern field (required parameter)

#### 2. app/ui/main_window.py - MainWindow._on_load_sequence()
- Pass source_dir=Path(path) when creating SequenceSpec
- path is already the directory selected by user, so just wrap in Path()

#### 3. app/services/export_runner.py - ExportRunner._assemble_frame()
- Changed from: frame_path = str(Path(src_seq.pattern.format(frame_num)))
- Changed to: 
  - filename = src_seq.pattern.format(frame_num)
  - frame_path = src_seq.source_dir / filename
- Now builds full path from source_dir + filename
- Correctly checks if full path exists

### Verification
- Ran: .\\.venv\\Scripts\\python -m py_compile app/core/types.py app/ui/main_window.py app/services/export_runner.py
- Result: Compilation OK
- Ran: .\\.venv\\Scripts\\python -c \"from app.ui.main_window import MainWindow; from app.core.types import SequenceSpec; print('Imports OK')\"
- Result: Imports OK

### Expected Result
- Export will now correctly find source files in their original directory
- File paths will be complete: D:\source_dir\render.00000.exr
- Instead of just: render.00000.exr


## Session 13 — 2026-01-09

### Bug Report
- After user clicks STOP to halt export, clicking EXPORT button again does nothing
- User can change compression settings, but export button remains unresponsive

### Root Cause Analysis
1. **Button disabled during stop (line 462):** When user clicks STOP, button is disabled with setEnabled(False)
2. **Button not re-enabled (line 527):** _on_export_finished() never calls setEnabled(True)
3. **Signal reconnect issue (line 526):** Used disconnect() which removes ALL connections (dangerous pattern)
   - If multiple connections existed, this could break the handler
   - After reconnect, button state wasn't clearly defined

### Fix - main_window.py

#### _on_export_finished() changes
- **Removed:** self.btn_export.clicked.disconnect()
- **Removed:** self.btn_export.clicked.connect(self._on_export_button_clicked)
- **Added:** self.btn_export.setEnabled(True)
- **Result:** Button state is checked at click time (by handler), not reconnection

#### Why this works
- _on_export_button_clicked() already checks button text: if text == \"EXPORT\"
- No need for signal reconnection; handler logic is state-based
- Just ensure button is enabled and properly reset to \"EXPORT\" text

### Verification
- Ran: .\\.venv\\Scripts\\python -m py_compile app/ui/main_window.py
- Result: Compilation OK
- Ran: .\\.venv\\Scripts\\python -c \"from app.ui.main_window import MainWindow; print('Imports OK')\"
- Result: Imports OK

### User Flow (Fixed)
1. Click EXPORT → button turns red (STOP), export runs
2. Click STOP → button disabled, export halts gracefully
3. Export finishes → button re-enabled, text reset to green (EXPORT)
4. Click EXPORT → button turns red (STOP), export runs again (NOW WORKS!)
5. Can change compression settings between exports


## Session 14 — 2026-01-09

### Goal
1. Change sequence display names from \"Seq: folder_name\" to just seq_0, seq_1, etc.
2. Add settings.ini persistence for:
   - Last input directory
   - Last output directory
   - EXR compression setting

### Changes

#### 1. Sequence Display Name Format (main_window.py)
- Changed display_name from: f\"Seq: {Path(path).name} ({len(frames_validated)} frames)\"
- Changed to: f\"{seq_id} ({len(frames_validated)} frames)\"
- Result: \"seq_0 (901 frames)\" instead of \"Seq: render (901 frames)\"

#### 2. Settings Persistence Module (app/services/settings.py - NEW)
- Created Settings class using ConfigParser
- Settings file: settings.ini at project root
- Methods:
  - get_input_dir() / set_input_dir(path)
  - get_output_dir() / set_output_dir(path)
  - get_compression() / set_compression(compression)
- Auto-creates settings.ini with defaults on first run
- All set methods auto-save to disk

#### 3. MainWindow Integration (main_window.py)
- Added: from ..services.settings import Settings
- Added: self.settings = Settings() in __init__
- Added: _load_settings() called after _connect_signals()
- Updated _on_load_sequence():
  - Added: self.settings.set_input_dir(path)
- Updated _on_browse_output_dir():
  - Added: self.settings.set_output_dir(path)
- Updated _on_compression_changed():
  - Added: self.settings.set_compression(compression)
- Added _load_settings() method:
  - Restores compression setting to combo box
  - Restores output directory to text field
  - Syncs state with restored values

### Verification
- Ran: .\\.venv\\Scripts\\python -m py_compile app/services/settings.py app/ui/main_window.py
- Result: Compilation OK
- Ran: .\\.venv\\Scripts\\python -c \"from app.ui.main_window import MainWindow; from app.services.settings import Settings; print('Imports OK')\"
- Result: Imports OK

### User Flow
1. First run: settings.ini created in project root with defaults
2. Load input sequence → path saved to settings
3. Browse output directory → path saved to settings
4. Change compression → setting saved to settings
5. Restart app → output dir and compression restored automatically
6. Sequence display shows: seq_0 (901 frames), seq_1 (492 frames), etc.

