"""
Main application window (Qt 6).

Orchestrates the three main panels:
- Input: Load/inspect sequences
- Output: Build output channel set
- Export: Configure export and run
"""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QTabWidget,
    QDialog,
    QLineEdit,
    QFileDialog,
    QListView,
    QComboBox,
)
from PySide6.QtCore import Qt

from ..core import (
    SequenceSpec,
    SequencePathPattern,
    OutputChannel,
    ChannelSourceRef,
    ValidationEngine,
    ValidationSeverity,
    FrameRangePolicy,
)
from ..oiio import OiioAdapter
from ..core.sequence import SequenceDiscovery
from ..services import ProjectState, ExportManager
from ..services.settings import Settings
from ..ui.models import (
    SequenceListModel,
    ChannelListModel,
    OutputChannelListModel,
    AttributeListModel,
    AttributeTableModel,
)
from ..ui.widgets import AttributeEditor


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EXR Channel Recombiner")
        self.setGeometry(100, 100, 1600, 950)

        # Settings
        self.settings = Settings()

        # State
        self.state = ProjectState()
        self.export_manager = ExportManager()

        # Models
        self.seq_list_model = SequenceListModel()
        self.ch_list_model = ChannelListModel()
        self.out_ch_list_model = OutputChannelListModel()
        self.attr_list_model = AttributeListModel()
        self.attr_table_model = AttributeTableModel()

        # Build UI
        self._build_ui()
        self._connect_signals()
        self._load_settings()

    def _build_ui(self) -> None:
        """Build the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)

        # Left panel: Input sequences
        left_panel = self._create_input_panel()
        main_layout.addWidget(left_panel, 1)

        # Center panel: Output channels
        center_panel = self._create_output_panel()
        main_layout.addWidget(center_panel, 1)

        # Right panel: Export settings + log
        right_panel = self._create_export_panel()
        main_layout.addWidget(right_panel, 1)

        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

    def _create_input_panel(self) -> QWidget:
        """Input sequence panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Input Sequences"))

        self.sequence_list = QListView()
        self.sequence_list.setModel(self.seq_list_model)
        self.sequence_list.clicked.connect(self._on_sequence_selected)
        layout.addWidget(self.sequence_list)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Load Sequence")
        btn_add.clicked.connect(self._on_load_sequence)
        btn_remove = QPushButton("Remove")
        btn_remove.clicked.connect(self._on_remove_sequence)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        layout.addLayout(btn_layout)

        layout.addWidget(QLabel("Channels in Selected Sequence"))
        self.channel_list = QListView()
        self.channel_list.setModel(self.ch_list_model)
        self.channel_list.setSelectionMode(QListView.SelectionMode.MultiSelection)
        layout.addWidget(self.channel_list)

        btn_add_to_output = QPushButton("Add Selected to Output")
        btn_add_to_output.clicked.connect(self._on_add_channel_to_output)
        layout.addWidget(btn_add_to_output)

        layout.addWidget(QLabel("Attributes"))
        self.attribute_list = QListView()
        self.attribute_list.setModel(self.attr_list_model)
        self.attribute_list.setSelectionMode(QListView.SelectionMode.MultiSelection)
        layout.addWidget(self.attribute_list)

        btn_add_attrs = QPushButton("Add Selected to Output Attributes")
        btn_add_attrs.clicked.connect(self._on_add_attributes_to_output)
        layout.addWidget(btn_add_attrs)

        layout.addStretch()
        return panel

    def _create_output_panel(self) -> QWidget:
        """Output channel builder panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Output Channels"))

        self.output_list = QListView()
        self.output_list.setModel(self.out_ch_list_model)
        layout.addWidget(self.output_list)

        btn_layout = QHBoxLayout()
        btn_remove = QPushButton("Remove")
        btn_remove.clicked.connect(self._on_remove_output_channel)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Tabs for attributes and options
        tabs = QTabWidget()

        # Output attributes
        attr_widget = QWidget()
        attr_layout = QVBoxLayout(attr_widget)
        self.attr_editor = AttributeEditor()
        attr_layout.addWidget(self.attr_editor)
        tabs.addTab(attr_widget, "Attributes")

        # Output options (compression, etc)
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)
        
        options_layout.addWidget(QLabel("Compression:"))
        self.compression_combo = QComboBox()
        self.compression_combo.addItems(["none", "rle", "zip", "zips", "piz", "pxr24", "b44", "b44a", "dwaa", "dwab"])
        self.compression_combo.currentTextChanged.connect(self._on_compression_changed)
        options_layout.addWidget(self.compression_combo)
        
        options_layout.addWidget(QLabel("Frame Policy:"))
        self.frame_policy_combo = QComboBox()
        self.frame_policy_combo.addItems(["Stop at Shortest", "Hold Last Frame", "Process Available"])
        self.frame_policy_combo.currentTextChanged.connect(self._on_frame_policy_changed)
        options_layout.addWidget(self.frame_policy_combo)
        
        options_layout.addStretch()
        tabs.addTab(options_widget, "Options")

        layout.addWidget(tabs, 1)

        return panel

    def _create_export_panel(self) -> QWidget:
        """Export settings and log panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Export Settings"))

        # Output directory
        layout.addWidget(QLabel("Output Directory:"))
        dir_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        dir_btn = QPushButton("Browse...")
        dir_btn.clicked.connect(self._on_browse_output_dir)
        dir_layout.addWidget(self.output_dir_edit)
        dir_layout.addWidget(dir_btn)
        layout.addLayout(dir_layout)

        # Filename pattern
        layout.addWidget(QLabel("Filename Pattern:"))
        self.filename_pattern_edit = QLineEdit()
        self.filename_pattern_edit.setText("output.%04d.exr")
        self.filename_pattern_edit.textChanged.connect(self._on_filename_pattern_changed)
        layout.addWidget(self.filename_pattern_edit)

        # Progress bar
        layout.addWidget(QLabel("Progress:"))
        self.progress_bar = QTextEdit()
        self.progress_bar.setMaximumHeight(40)
        self.progress_bar.setReadOnly(True)
        layout.addWidget(self.progress_bar)

        # Export button
        self.btn_export = QPushButton("EXPORT")
        self.btn_export.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;"
        )
        self.btn_export.clicked.connect(self._on_export_button_clicked)
        layout.addWidget(self.btn_export)

        # Log
        layout.addWidget(QLabel("Log:"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

        return panel

    def _connect_signals(self) -> None:
        """Connect signals from services to UI."""
        self.export_manager.progress.connect(self._on_export_progress)
        self.export_manager.log.connect(self._on_export_log)
        self.export_manager.finished.connect(self._on_export_finished)
        self.attr_editor.attributes_changed.connect(self._on_attributes_changed)

    # ========== Sequence Management ==========

    def _on_load_sequence(self) -> None:
        """Handle 'Load Sequence' button."""
        initial_dir = self.settings.get_input_dir() or ""
        path = QFileDialog.getExistingDirectory(self, "Select Sequence Directory", initial_dir)
        if not path:
            return

        # Auto-discover sequences in the directory
        discovered = SequenceDiscovery.discover_sequences(path)
        if not discovered:
            self._append_log(f"[ERROR] No image sequences found in directory: {path}")
            return

        # If multiple sequences, let user choose; if one, use it directly
        if len(discovered) == 1:
            pattern_str, frames = discovered[0]
        else:
            pattern_str, frames = self._ask_sequence_selection_dialog(discovered)
            if pattern_str is None:
                return

        # Confirm/show the discovered sequence
        if frames is not None:
            self._append_log(f"[INFO] Auto-discovered sequence: {pattern_str} ({len(frames)} frames)")
        else:
            self._append_log(f"[INFO] Auto-discovered sequence: {pattern_str}")

        # Discover frames again to validate
        frames_validated = SequenceDiscovery.discover_frames(pattern_str, path)
        if not frames_validated:
            self._append_log(f"[ERROR] No frames found matching pattern: {pattern_str}")
            return

        # Probe first frame
        pattern = SequencePathPattern(pattern_str)
        first_frame_path = str(Path(path) / pattern.format(frames_validated[0]))

        probe = OiioAdapter.probe_file(first_frame_path)
        if not probe:
            self._append_log(f"[ERROR] Failed to probe file: {first_frame_path}")
            return

        # Create sequence spec
        seq_id = f"seq_{len(self.state.sequences)}"
        seq = SequenceSpec(
            id=seq_id,
            display_name=f"{seq_id} ({len(frames_validated)} frames)",
            pattern=pattern,
            source_dir=Path(path),
            frames=frames_validated,
            static_probe=probe,
        )

        self.state.add_sequence(seq)
        self.seq_list_model.add_sequence(seq)
        self.settings.set_input_dir(path)  # Save input directory to settings
        num_channels = probe.main_subimage.spec.nchannels if probe.main_subimage else 0
        self._append_log(
            f"[OK] Loaded sequence: {len(frames_validated)} frames, "
            f"{num_channels} channels"
        )

    def _on_remove_sequence(self) -> None:
        """Handle 'Remove' button for sequences."""
        current = self.sequence_list.currentIndex()
        if not current.isValid():
            return

        seq = self.seq_list_model.get_sequence(current.row())
        if seq:
            self.state.remove_sequence(seq.id)
            self.seq_list_model.remove_at(current.row())
            self.ch_list_model.set_channels([])
            self._append_log(f"[OK] Removed sequence: {seq.display_name}")

    def _on_sequence_selected(self, index) -> None:
        """Handle sequence selection."""
        seq = self.seq_list_model.get_sequence(index.row())
        if seq and seq.static_probe and seq.static_probe.main_subimage:
            channels = seq.static_probe.main_subimage.channels
            self.ch_list_model.set_channels(channels)
            
            # Populate attributes list
            attributes = []
            if seq.static_probe.main_subimage.attributes and seq.static_probe.main_subimage.attributes.attributes:
                attributes = seq.static_probe.main_subimage.attributes.attributes
            self.attr_list_model.set_attributes(attributes)
            
            self._append_log(f"[OK] Selected sequence: {seq.display_name} ({len(channels)} channels, {len(attributes)} attributes)")

    # ========== Output Channel Management ==========

    def _on_add_channel_to_output(self) -> None:
        """Handle 'Add Selected to Output' button."""
        seq_index = self.sequence_list.currentIndex()
        
        if not seq_index.isValid():
            self._append_log("[WARNING] Please select a sequence")
            return

        seq = self.seq_list_model.get_sequence(seq_index.row())
        if not seq:
            return

        # Get all selected channel indices (multi-select)
        selected_indices = self.channel_list.selectedIndexes()
        if not selected_indices:
            self._append_log("[WARNING] Please select at least one channel")
            return

        # Add each selected channel
        for ch_index in selected_indices:
            ch = self.ch_list_model.get_channel(ch_index.row())
            if not ch:
                continue

            # Create output channel
            output_ch = OutputChannel(
                output_name=ch.name,
                source=ChannelSourceRef(
                    sequence_id=seq.id,
                    channel_name=ch.name,
                    subimage_index=0,
                ),
            )

            self.state.add_output_channel(output_ch)
            self.out_ch_list_model.add_channel(output_ch)
            self._append_log(f"[OK] Added output channel: {ch.name}")

    def _on_remove_output_channel(self) -> None:
        """Handle 'Remove' button for output channels."""
        current = self.output_list.currentIndex()
        if not current.isValid():
            return

        ch = self.out_ch_list_model.get_channel(current.row())
        if ch:
            self.state.remove_output_channel(current.row())
            self.out_ch_list_model.remove_at(current.row())
            self._append_log(f"[OK] Removed output channel: {ch.output_name}")

    def _on_add_attributes_to_output(self) -> None:
        """Handle 'Add Selected to Output Attributes' button."""
        # Get all selected attribute indices (multi-select)
        selected_indices = self.attribute_list.selectedIndexes()
        if not selected_indices:
            self._append_log("[WARNING] Please select at least one attribute")
            return

        # Add each selected attribute to the attribute editor
        for attr_index in selected_indices:
            attr = self.attr_list_model.get_attribute(attr_index.row())
            if attr:
                self.attr_editor.model.add_attribute(attr)
                self._append_log(f"[OK] Added output attribute: {attr.name}")

        # Notify of change
        self.attr_editor.attributes_changed.emit(self.attr_editor.get_attributes())

    # ========== Attribute Management ==========

    def _on_attributes_changed(self, attrs) -> None:
        """Handle attribute changes."""
        self.state.set_output_attributes(attrs)
        self._append_log(f"[OK] Updated attributes: {len(attrs.attributes)} attributes")

    def _on_import_attributes_from_source(self) -> None:
        """Handle 'Edit Attribute' button in attribute editor."""
        # This handler remains for potential future use
        # The "Edit Attribute" button in AttributeEditor will open a dialog for editing
        pass

    # ========== Export Settings ==========

    def _on_browse_output_dir(self) -> None:
        """Handle 'Browse...' for output directory."""
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_dir_edit.setText(path)
            self.state.set_output_dir(path)
            self.settings.set_output_dir(path)  # Save to settings

    def _on_filename_pattern_changed(self, text: str) -> None:
        """Handle filename pattern change."""
        self.state.set_filename_pattern(text)

    def _on_compression_changed(self, compression: str) -> None:
        """Handle compression selection."""
        self.state.set_compression(compression)
        self.settings.set_compression(compression)  # Save to settings

    def _on_frame_policy_changed(self, policy_text: str) -> None:
        """Handle frame policy selection."""
        # Map display text to enum
        policy_map = {
            "Stop at Shortest": FrameRangePolicy.STOP_AT_SHORTEST,
            "Hold Last Frame": FrameRangePolicy.HOLD_LAST,
            "Process Available": FrameRangePolicy.PROCESS_AVAILABLE,
        }
        policy = policy_map.get(policy_text, FrameRangePolicy.STOP_AT_SHORTEST)
        self.state.export_spec.frame_policy = policy

    # ========== Export ==========

    def _on_export_button_clicked(self) -> None:
        """Handle export button click (toggles between EXPORT and STOP)."""
        if self.btn_export.text() == "EXPORT":
            self._on_export()
        else:  # STOP mode
            self.export_manager.stop_export()
            self.btn_export.setEnabled(False)
            self._append_log("[USER] Export stop requested...")

    def _on_export(self) -> None:
        """Handle 'EXPORT' button."""
        # Update state from UI
        output_dir = self.output_dir_edit.text()
        if not output_dir:
            self._append_log("[ERROR] Output directory not set")
            return

        self.state.set_output_dir(output_dir)
        self.state.set_filename_pattern(self.filename_pattern_edit.text())
        self.state.set_compression(self.compression_combo.currentText())

        # Validate
        export_spec = self.state.get_export_spec()
        issues = ValidationEngine.validate_export(export_spec, self.state.sequences)

        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]

        self._append_log(f"\n[VALIDATION] {len(errors)} errors, {len(warnings)} warnings")
        for issue in errors:
            self._append_log(f"  ERROR: {issue}")
        for issue in warnings:
            self._append_log(f"  WARNING: {issue}")

        if errors:
            self._append_log("[BLOCKED] Export blocked due to validation errors")
            return

        # Start export
        self._append_log("\n[EXPORT] Starting export...")
        
        # Change button to STOP mode
        self.btn_export.setText("STOP")
        self.btn_export.setStyleSheet(
            "background-color: #f44336; color: white; font-weight: bold; font-size: 14px;"
        )
        
        self.export_manager.start_export(export_spec, self.state.sequences)

    def _on_export_progress(self, percent: int, message: str) -> None:
        """Handle export progress."""
        self.progress_bar.setText(f"{percent}% - {message}")

    def _on_export_log(self, message: str) -> None:
        """Handle export log messages."""
        self._append_log(f"[EXPORT] {message}")

    def _on_export_finished(self, success: bool, message: str) -> None:
        """Handle export completion."""
        if success:
            self._append_log(f"\n[SUCCESS] {message}")
        else:
            self._append_log(f"\n[FAILED] {message}")
        self.progress_bar.setText("")
        # Reset button to EXPORT mode
        self.btn_export.setText("EXPORT")
        self.btn_export.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;"
        )
        self.btn_export.setEnabled(True)

    # ========== Utilities ==========

    def _append_log(self, message: str) -> None:
        """Append to log."""
        self.log.append(message)

    def _ask_pattern_dialog(self) -> tuple[str, bool]:
        """Ask user for sequence pattern."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Sequence Pattern")
        layout = QVBoxLayout(dialog)

        layout.addWidget(
            QLabel("Enter sequence pattern (e.g., image.%04d.exr or image.####.exr):")
        )
        edit = QLineEdit()
        edit.setText("image.%04d.exr")
        layout.addWidget(edit)

        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        ok = dialog.exec() == QDialog.DialogCode.Accepted
        return edit.text(), ok

    def _ask_sequence_selection_dialog(
        self, sequences: list[tuple[str, list[int]]]
    ) -> tuple[Optional[str], Optional[list[int]]]:
        """Show dialog for user to select from multiple sequences."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Sequence")
        dialog.setGeometry(400, 300, 500, 300)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Multiple sequences detected. Select one:"))

        combo = QComboBox()
        for pattern, frames in sequences:
            combo.addItem(f"{pattern} ({len(frames)} frames)", (pattern, frames))
        layout.addWidget(combo)

        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        ok = dialog.exec() == QDialog.DialogCode.Accepted
        if ok:
            pattern, frames = combo.currentData()
            return pattern, frames
        return None, None
    # ========== Settings ==========

    def _load_settings(self) -> None:
        """Load saved settings and restore UI state."""
        # Load compression setting
        saved_compression = self.settings.get_compression()
        idx = self.compression_combo.findText(saved_compression)
        if idx >= 0:
            self.compression_combo.setCurrentIndex(idx)

        # Load output directory
        saved_output_dir = self.settings.get_output_dir()
        if saved_output_dir:
            self.output_dir_edit.setText(saved_output_dir)
            self.state.set_output_dir(saved_output_dir)