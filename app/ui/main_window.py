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
    QTableView,
    QComboBox,
    QSpinBox,
    QProgressDialog,
    QMessageBox,
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
    AttributeSpec,
    AttributeSource,
)
from ..oiio import OiioAdapter
from ..core.sequence import SequenceDiscovery
from ..services import ProjectState, ExportManager, ProjectSerializer
from ..services.settings import Settings
from ..ui.models import (
    SequenceListModel,
    ChannelListModel,
    OutputChannelListModel,
    AttributeTableModel,
)
from ..ui.widgets import AttributeEditor, ProcessingWidget


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EXR Toolkit")
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
        self.attr_table_model = AttributeTableModel()

        # Track longest sequence for frame range limits
        self.max_frame_count = 0

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

        # Input Sequences section
        layout.addWidget(QLabel("Input Sequences"))
        self.sequence_list = QListView()
        self.sequence_list.setModel(self.seq_list_model)
        self.sequence_list.clicked.connect(self._on_sequence_selected)
        layout.addWidget(self.sequence_list, 1)  # Stretch factor 1

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Load Sequence")
        btn_add.clicked.connect(self._on_load_sequence)
        btn_remove = QPushButton("Remove")
        btn_remove.clicked.connect(self._on_remove_sequence)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        layout.addLayout(btn_layout)

        # Channels section
        layout.addWidget(QLabel("Channels in Selected Sequence"))
        self.channel_list = QListView()
        self.channel_list.setModel(self.ch_list_model)
        self.channel_list.setSelectionMode(QListView.SelectionMode.MultiSelection)
        layout.addWidget(self.channel_list, 1)  # Stretch factor 1

        btn_add_to_output = QPushButton("Add Selected to Output")
        btn_add_to_output.clicked.connect(self._on_add_channel_to_output)
        layout.addWidget(btn_add_to_output)

        # Source Attributes section
        layout.addWidget(QLabel("Source Attributes"))
        self.source_attribute_table = QTableView()
        self.source_attribute_table.setModel(self.attr_table_model)
        self.source_attribute_table.horizontalHeader().setStretchLastSection(True)
        self.source_attribute_table.verticalHeader().setVisible(False)
        from PySide6.QtWidgets import QAbstractItemView
        self.source_attribute_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.source_attribute_table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        layout.addWidget(self.source_attribute_table, 1)  # Stretch factor 1

        btn_add_attrs = QPushButton("Add Selected to Output Attributes")
        btn_add_attrs.clicked.connect(self._on_add_attributes_to_output)
        layout.addWidget(btn_add_attrs)

        return panel

    def _create_output_panel(self) -> QWidget:
        """Output channel builder panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Output Channels"))

        self.output_list = QListView()
        self.output_list.setModel(self.out_ch_list_model)
        self.output_list.setSelectionMode(QListView.SelectionMode.MultiSelection)
        layout.addWidget(self.output_list, 1)  # Stretch factor 1

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

        # Image processing
        self.processing_widget = ProcessingWidget(self.state.processing_pipeline)
        self.processing_widget.config_changed.connect(self._on_processing_config_changed)
        tabs.addTab(self.processing_widget, "Processing")

        # Output options (compression, etc)
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)
        
        options_layout.addWidget(QLabel("Compression:"))
        self.compression_combo = QComboBox()
        self.compression_combo.addItems(["none", "rle", "zip", "zips", "piz", "pxr24", "b44", "b44a", "dwaa", "dwab"])
        self.compression_combo.setToolTip(
            "Select compression method for output EXR files:\n"
            "  • none: Uncompressed (largest file size)\n"
            "  • rle: Run-length encoding (lossless, moderate compression)\n"
            "  • zip: ZIP compression (lossless, good for noise)\n"
            "  • zips: ZIP single-scanline (less memory)\n"
            "  • piz: PIZ wavelet (lossless, best quality/compression)\n"
            "  • pxr24: PXR24 (lossless, 24-bit precision)\n"
            "  • b44: B44 (lossy, medium compression)\n"
            "  • b44a: B44A (lossy with alpha, improved)\n"
            "  • dwaa: DWAA (lossy, DCT-based, good speed)\n"
            "  • dwab: DWAB (lossy, DCT-based, better compression)"
        )
        self.compression_combo.currentTextChanged.connect(self._on_compression_changed)
        options_layout.addWidget(self.compression_combo)
        
        options_layout.addWidget(QLabel("Frame Policy:"))
        self.frame_policy_combo = QComboBox()
        self.frame_policy_combo.addItems(["Stop at Shortest", "Hold Last Frame", "Process Available"])
        self.frame_policy_combo.setToolTip(
            "Define behavior when input sequences have different lengths:\n"
            "  • Stop at Shortest: Export only frames present in all sequences (safe)\n"
            "  • Hold Last Frame: Extend shorter sequences using their last frame\n"
            "  • Process Available: Export all available frames (may have gaps)"
        )
        self.frame_policy_combo.currentTextChanged.connect(self._on_frame_policy_changed)
        options_layout.addWidget(self.frame_policy_combo)

        options_layout.addWidget(QLabel("Compression Policy:"))
        self.compression_policy_combo = QComboBox()
        self.compression_policy_combo.addItem("Skip matching compression for single input(default)", "skip")
        self.compression_policy_combo.addItem("Always recompress", "always")
        self.compression_policy_combo.setToolTip(
            "Skip matching compression for single input: Fast optimization for single-source exports with no channel modifications.\n"
            "Only works when:\n"
            "  • Exporting from a single input sequence\n"
            "  • No channels are added, removed, or renamed\n"
            "  • Useful for attribute editing workflows\n\n"
            "Always recompress: Standard export path for multi-source composites or channel modifications."
        )
        self.compression_policy_combo.currentIndexChanged.connect(
            self._on_compression_policy_changed
        )
        options_layout.addWidget(self.compression_policy_combo)
        
        # Project save/load buttons
        options_layout.addWidget(QLabel("Project Management:"))
        project_btn_layout = QHBoxLayout()
        btn_save_project = QPushButton("Save Project")
        btn_save_project.clicked.connect(self._on_save_project)
        btn_load_project = QPushButton("Load Project")
        btn_load_project.clicked.connect(self._on_load_project)
        project_btn_layout.addWidget(btn_save_project)
        project_btn_layout.addWidget(btn_load_project)
        project_btn_layout.addStretch()
        options_layout.addLayout(project_btn_layout)
        
        options_layout.addStretch()
        tabs.addTab(options_widget, "Options")

        layout.addWidget(tabs, 1)  # Stretch factor 1

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

        # Frame range selector
        layout.addWidget(QLabel("Processing Frame Range:"))
        range_layout = QHBoxLayout()
        
        range_layout.addWidget(QLabel("In Frame:"))
        self.in_frame_spinbox = QSpinBox()
        self.in_frame_spinbox.setMinimum(0)
        self.in_frame_spinbox.setMaximum(999999)
        self.in_frame_spinbox.setValue(0)
        self.in_frame_spinbox.valueChanged.connect(self._on_in_frame_changed)
        range_layout.addWidget(self.in_frame_spinbox)
        
        range_layout.addWidget(QLabel("Out Frame:"))
        self.out_frame_spinbox = QSpinBox()
        self.out_frame_spinbox.setMinimum(0)
        self.out_frame_spinbox.setMaximum(999999)
        self.out_frame_spinbox.setValue(0)
        self.out_frame_spinbox.valueChanged.connect(self._on_out_frame_changed)
        range_layout.addWidget(self.out_frame_spinbox)
        
        self.max_frame_label = QLabel("(Max: 0 frames)")
        range_layout.addWidget(self.max_frame_label)
        range_layout.addStretch()
        layout.addLayout(range_layout)

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

        # Create and show loading dialog
        loading_dialog = QProgressDialog("Loading sequence...", "", 0, 0, self)
        loading_dialog.setWindowTitle("Loading")
        loading_dialog.setCancelButton(None)
        loading_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        loading_dialog.show()

        # Process events to show dialog
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            # Auto-discover sequences in the directory
            self._append_log("[LOAD] Discovering sequences in directory...")
            QApplication.processEvents()
            discovered = SequenceDiscovery.discover_sequences(path)
            if not discovered:
                loading_dialog.close()
                self._append_log(f"[ERROR] No image sequences found in directory: {path}")
                return

            self._append_log(f"[LOAD] Found {len(discovered)} sequence(s)")
            QApplication.processEvents()

            # If multiple sequences, let user choose; if one, use it directly
            if len(discovered) == 1:
                pattern_str, frames = discovered[0]
                self._append_log(f"[LOAD] Using sequence: {pattern_str}")
                QApplication.processEvents()
            else:
                loading_dialog.close()
                pattern_str, frames = self._ask_sequence_selection_dialog(discovered)
                if pattern_str is None:
                    return
                loading_dialog = QProgressDialog("Loading sequence...", "", 0, 0, self)
                loading_dialog.setWindowTitle("Loading")
                loading_dialog.setCancelButton(None)
                loading_dialog.setWindowModality(Qt.WindowModality.WindowModal)
                loading_dialog.show()
                QApplication.processEvents()

            # Confirm/show the discovered sequence
            if frames is not None:
                self._append_log(f"[LOAD] Initial scan found {len(frames)} frame(s): {pattern_str}")
            else:
                self._append_log(f"[LOAD] Pattern recognized: {pattern_str}")
            QApplication.processEvents()

            # Discover frames again to validate
            self._append_log("[LOAD] Validating and discovering all frames...")
            QApplication.processEvents()
            frames_validated = SequenceDiscovery.discover_frames(pattern_str, path)
            if not frames_validated:
                loading_dialog.close()
                self._append_log(f"[ERROR] No frames found matching pattern: {pattern_str}")
                return

            self._append_log(f"[LOAD] Discovered {len(frames_validated)} frame(s)")
            QApplication.processEvents()

            # Probe first frame
            self._append_log("[LOAD] Probing first frame to extract metadata...")
            QApplication.processEvents()
            pattern = SequencePathPattern(pattern_str)
            first_frame_path = str(Path(path) / pattern.format(frames_validated[0]))

            probe = OiioAdapter.probe_file(first_frame_path)
            if not probe:
                loading_dialog.close()
                self._append_log(f"[ERROR] Failed to probe file: {first_frame_path}")
                return

            self._append_log("[LOAD] Metadata extraction complete")
            QApplication.processEvents()

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
            num_attributes = len(probe.main_subimage.attributes.attributes) if probe.main_subimage and probe.main_subimage.attributes else 0
            self._append_log(
                f"[OK] Loaded sequence: {len(frames_validated)} frames, "
                f"{num_channels} channels, {num_attributes} attributes"
            )
            # Update max frame count
            self._update_max_frame_count()
            QApplication.processEvents()
        finally:
            loading_dialog.close()

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
            self._update_max_frame_count()
            self._append_log(f"[OK] Removed sequence: {seq.display_name}")

    def _on_sequence_selected(self, index) -> None:
        """Handle sequence selection."""
        seq = self.seq_list_model.get_sequence(index.row())
        if not seq:
            return
        
        # Check if we have probe data
        if not seq.static_probe or not seq.static_probe.main_subimage:
            # No probe data - this can happen after loading a project
            self.ch_list_model.set_channels([])
            self.attr_table_model.set_attributes([])
            self._append_log(
                f"[INFO] Sequence '{seq.display_name}' has no metadata. "
                f"Click 'Load Sequence' and select this sequence's directory to load metadata."
            )
            return
        
        # Probe data available - populate channels and attributes
        channels = seq.static_probe.main_subimage.channels
        self.ch_list_model.set_channels(channels)
        
        # Populate attributes table
        attributes = []
        if seq.static_probe.main_subimage.attributes and seq.static_probe.main_subimage.attributes.attributes:
            attributes = seq.static_probe.main_subimage.attributes.attributes
        self.attr_table_model.set_attributes(attributes)
        
        # Update max frame count from longest sequence
        self._update_max_frame_count()
        
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
        """Handle 'Remove' button for output channels (multi-select support)."""
        # Get all selected indices (multi-select)
        selected_indices = self.output_list.selectedIndexes()
        if not selected_indices:
            self._append_log("[WARNING] Please select at least one output channel")
            return

        # Sort indices in reverse order to remove from highest to lowest
        # This preserves indices for remaining items
        rows_to_remove = sorted([idx.row() for idx in selected_indices], reverse=True)

        for row in rows_to_remove:
            ch = self.out_ch_list_model.get_channel(row)
            if ch:
                self.state.remove_output_channel(row)
                self.out_ch_list_model.remove_at(row)
                self._append_log(f"[OK] Removed output channel: {ch.output_name}")

    def _on_add_attributes_to_output(self) -> None:
        """Handle 'Add Selected to Output Attributes' button."""
        # Get all selected attribute indices from table (multi-select)
        selected_indices = self.source_attribute_table.selectedIndexes()
        if not selected_indices:
            self._append_log("[WARNING] Please select at least one attribute")
            return

        # Get unique row indices
        rows_to_add = set(idx.row() for idx in selected_indices)

        # Add each selected attribute to the attribute editor
        for row in rows_to_add:
            attr = self.attr_table_model.get_attribute(row)
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
        
        # Update the compression attribute in output attributes if it exists
        compression_attr = AttributeSpec(
            name="compression",
            oiio_type="string",
            value=compression,
            source=AttributeSource.CUSTOM,
            editable=True,
        )
        self.state.add_output_attribute(compression_attr)
        self.attr_editor.model.add_attribute(compression_attr)
        self.attr_editor.attributes_changed.emit(self.attr_editor.get_attributes())

    def _on_processing_config_changed(self) -> None:
        """Handle processing pipeline configuration changes."""
        # Update the pipeline in state
        self.state.set_processing_pipeline(self.processing_widget.get_pipeline())

    def _on_frame_policy_changed(self, policy_text: str) -> None:
        """Handle frame policy selection."""
        policy = self._get_frame_policy_from_text(policy_text)
        self.state.export_spec.frame_policy = policy
        
        # Save to settings
        policy_reverse_map = {
            "Stop at Shortest": "STOP_AT_SHORTEST",
            "Hold Last Frame": "HOLD_LAST",
            "Process Available": "PROCESS_AVAILABLE",
        }
        policy_name = policy_reverse_map.get(policy_text, "STOP_AT_SHORTEST")
        self.settings.set_frame_policy(policy_name)

    def _get_frame_policy_from_text(self, policy_text: str) -> FrameRangePolicy:
        """Convert display text to FrameRangePolicy enum."""
        policy_map = {
            "Stop at Shortest": FrameRangePolicy.STOP_AT_SHORTEST,
            "Hold Last Frame": FrameRangePolicy.HOLD_LAST,
            "Process Available": FrameRangePolicy.PROCESS_AVAILABLE,
        }
        return policy_map.get(policy_text, FrameRangePolicy.STOP_AT_SHORTEST)

    # ========== Frame Range Management ==========

    def _update_max_frame_count(self) -> None:
        """Update max frame count from all loaded sequences."""
        self.max_frame_count = 0
        max_frame_number = 0  # Track highest frame NUMBER, not count
        
        for seq in self.state.sequences.values():
            if seq.frames:
                frame_count = len(seq.frames)
                if frame_count > self.max_frame_count:
                    self.max_frame_count = frame_count
                # Also track the actual highest frame number
                actual_max = max(seq.frames)
                if actual_max > max_frame_number:
                    max_frame_number = actual_max

        # Update spinbox limits and values
        # Use the actual highest frame number, not count - 1
        max_val = max_frame_number if self.max_frame_count > 0 else 0
        
        # Set spinbox maximum limits based on longest sequence
        self.in_frame_spinbox.setMaximum(max_val)
        self.out_frame_spinbox.setMaximum(max_val)
        
        # Reset values if no sequences
        if self.max_frame_count == 0:
            self.in_frame_spinbox.setValue(0)
            self.out_frame_spinbox.setValue(0)
            self.state.export_spec.frame_range = None
        else:
            # Initialize frame range to full sequence range [0, max_frame_number]
            self.in_frame_spinbox.setValue(0)
            self.out_frame_spinbox.setValue(max_val)
            self.state.export_spec.frame_range = (0, max_val)
        
        self.max_frame_label.setText(f"(Max: {self.max_frame_count} frames)")
        self._append_log(f"[OK] Frame range initialized: 0 to {max_val} ({self.max_frame_count} frames) [Max frame number: {max_frame_number}]")

    def _on_in_frame_changed(self, value: int) -> None:
        """Handle in frame spinbox change."""
        # Ensure in_frame <= out_frame
        if value > self.out_frame_spinbox.value():
            self.out_frame_spinbox.setValue(value)
        
        self._update_export_frame_range()

    def _on_out_frame_changed(self, value: int) -> None:
        """Handle out frame spinbox change."""
        # Ensure out_frame >= in_frame
        if value < self.in_frame_spinbox.value():
            self.in_frame_spinbox.setValue(value)
        
        self._update_export_frame_range()

    def _update_export_frame_range(self) -> None:
        """Update export spec with current frame range."""
        in_frame = self.in_frame_spinbox.value()
        out_frame = self.out_frame_spinbox.value()
        
        if self.max_frame_count > 0:
            self.state.export_spec.frame_range = (in_frame, out_frame)
            self._append_log(f"[OK] Frame range set: {in_frame} to {out_frame}")

    def _on_compression_policy_changed(self, index: int) -> None:
        """Handle compression policy selection change."""
        policy = self.compression_policy_combo.currentData()
        self.settings.set_compression_policy(policy)
        policy_text = self.compression_policy_combo.itemText(index)
        self._append_log(f"[OK] Compression policy set to: {policy_text}")

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

        # Check for file overwrites before exporting
        if not self._check_output_file_overwrite(output_dir):
            return

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
        
        # Get compression policy
        compression_policy = self.compression_policy_combo.currentData()
        self._append_log(f"[DEBUG] Compression policy selected: {compression_policy}")
        
        # Get processing pipeline
        processing_pipeline = self.state.get_processing_pipeline()
        
        self.export_manager.start_export(
            export_spec,
            self.state.sequences,
            compression_policy,
            processing_pipeline,
        )

    def _on_export_progress(self, percent: int, message: str) -> None:
        """Handle export progress."""
        self.progress_bar.setText(f"{percent}% - {message}")

    def _on_export_log(self, message: str) -> None:
        """Handle export log messages."""
        self._append_log(f"[EXPORT] {message}")

    def _check_output_file_overwrite(self, output_dir: str) -> bool:
        """Check if output files would overwrite existing files. Return False if user cancels."""
        pattern = self.filename_pattern_edit.text()
        if not pattern:
            return True
        
        # Check for potential overwrites by looking at first few frames
        existing_files = []
        export_spec = self.state.get_export_spec()
        frame_list = self._resolve_frame_list()
        
        # Check first 3 frames as a sample
        for frame_num in frame_list[:3]:
            output_path = Path(output_dir) / self._format_filename(pattern, frame_num)
            if output_path.exists():
                existing_files.append(output_path.name)
        
        if existing_files:
            # Show confirmation dialog
            msg = f"Output files already exist and will be overwritten:\n\n"
            msg += "\n".join(existing_files[:5])
            if len(existing_files) > 5:
                msg += f"\n... and {len(existing_files) - 5} more"
            msg += f"\n\nContinue with export?"
            
            reply = QMessageBox.warning(
                self,
                "Files Will Be Overwritten",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            return reply == QMessageBox.StandardButton.Yes
        
        return True

    def _resolve_frame_list(self) -> list[int]:
        """Get list of frames to export."""
        if not self.state.sequences:
            return []
        all_frames = []
        for seq in self.state.sequences.values():
            all_frames.extend(seq.frames)
        return sorted(set(all_frames))

    def _format_filename(self, pattern: str, frame: int) -> str:
        """Format filename with frame number."""
        import re
        result = pattern
        result = re.sub(r"%0(\d+)d", lambda m: str(frame).zfill(int(m.group(1))), result)
        result = re.sub(r"#+", lambda m: str(frame).zfill(len(m.group(0))), result)
        return result

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

        # Load frame policy setting
        saved_frame_policy = self.settings.get_frame_policy()
        policy_map_reverse = {
            "STOP_AT_SHORTEST": "Stop at Shortest",
            "HOLD_LAST": "Hold Last Frame",
            "PROCESS_AVAILABLE": "Process Available",
        }
        policy_text = policy_map_reverse.get(saved_frame_policy, "Stop at Shortest")
        idx = self.frame_policy_combo.findText(policy_text)
        if idx >= 0:
            self.frame_policy_combo.setCurrentIndex(idx)
            self.state.export_spec.frame_policy = self._get_frame_policy_from_text(policy_text)

        # Load compression policy setting
        saved_compression_policy = self.settings.get_compression_policy()
        self._append_log(f"[SETTINGS] Loaded compression policy: {saved_compression_policy}")
        idx = self.compression_policy_combo.findData(saved_compression_policy)
        self._append_log(f"[SETTINGS] Found compression policy at index: {idx}")
        if idx >= 0:
            self.compression_policy_combo.setCurrentIndex(idx)
            self._append_log(f"[SETTINGS] Set compression policy combo to index {idx}")
        else:
            # Default to 'skip' if not found
            self.compression_policy_combo.setCurrentIndex(0)
            self._append_log(f"[SETTINGS] Compression policy not found, defaulting to index 0 (skip)")

        # Load output directory
        saved_output_dir = self.settings.get_output_dir()
        if saved_output_dir:
            self.output_dir_edit.setText(saved_output_dir)
            self.state.set_output_dir(saved_output_dir)

        # Add compression attribute to output attributes
        self._add_compression_attribute()

    def _add_compression_attribute(self) -> None:
        """Add compression attribute based on current compression setting."""
        compression = self.state.get_compression()
        compression_attr = AttributeSpec(
            name="compression",
            oiio_type="string",
            value=compression,
            source=AttributeSource.CUSTOM,
            editable=True,
        )
        self.state.add_output_attribute(compression_attr)
        self.attr_editor.model.add_attribute(compression_attr)

    # ========== Project Management ==========

    def _on_save_project(self) -> None:
        """Handle 'Save Project' button."""
        initial_dir = self.settings.get_project_dir() or ""
        file_path, ok = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            initial_dir,
            "EXR Toolkit Project Files (*.exrproj);;All Files (*)",
        )
        
        if not ok or not file_path:
            return

        try:
            project_path = Path(file_path)
            ProjectSerializer.save_to_file(self.state, project_path)
            self.settings.set_project_dir(str(project_path.parent))
            self._append_log(f"[OK] Project saved to: {project_path}")
        except Exception as e:
            self._append_log(f"[ERROR] Failed to save project: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to save project:\n{e}")

    def _on_load_project(self) -> None:
        """Handle 'Load Project' button."""
        initial_dir = self.settings.get_project_dir() or ""
        file_path, ok = QFileDialog.getOpenFileName(
            self,
            "Load Project",
            initial_dir,
            "EXR Toolkit Project Files (*.exrproj);;All Files (*)",
        )
        
        if not ok or not file_path:
            return

        try:
            project_path = Path(file_path)
            loaded_state = ProjectSerializer.load_from_file(project_path)
            self.settings.set_project_dir(str(project_path.parent))
            
            # Clear current state
            self.state.sequences.clear()
            self.state.export_spec.output_channels.clear()
            self.seq_list_model.clear_sequences()
            self.out_ch_list_model.clear_channels()
            self.ch_list_model.set_channels([])
            
            # Restore loaded state
            self.state = loaded_state
            
            # Reload sequences into model (note: probes will be None, user should reload them)
            for seq in self.state.list_sequences():
                self.seq_list_model.add_sequence(seq)
            
            # Auto-probe sequences to restore metadata
            self._append_log("[LOAD] Scanning source directories for file metadata...")
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            probed_count = 0
            for seq in self.state.list_sequences():
                if not seq.source_dir.exists():
                    self._append_log(f"[WARNING] Source directory not found: {seq.source_dir}")
                    continue
                
                # Probe first frame to get metadata
                if seq.frames:
                    try:
                        pattern = SequencePathPattern(seq.pattern.pattern)
                        first_frame_path = str(seq.source_dir / pattern.format(seq.frames[0]))
                        probe = OiioAdapter.probe_file(first_frame_path)
                        if probe:
                            seq.static_probe = probe
                            probed_count += 1
                            QApplication.processEvents()
                    except Exception as e:
                        self._append_log(f"[WARNING] Failed to probe {seq.display_name}: {e}")
            
            if probed_count > 0:
                self._append_log(f"[OK] Restored metadata for {probed_count} sequence(s)")
            
            # Reload output channels into model
            for ch in self.state.get_output_channels():
                self.out_ch_list_model.add_channel(ch)
            
            # Reload export settings into UI
            self.output_dir_edit.setText(self.state.get_output_dir())
            self.filename_pattern_edit.setText(self.state.get_filename_pattern())
            
            compression = self.state.get_compression()
            idx = self.compression_combo.findText(compression)
            if idx >= 0:
                self.compression_combo.setCurrentIndex(idx)
            
            frame_policy = self.state.export_spec.frame_policy
            policy_map = {
                FrameRangePolicy.STOP_AT_SHORTEST: "Stop at Shortest",
                FrameRangePolicy.HOLD_LAST: "Hold Last Frame",
                FrameRangePolicy.PROCESS_AVAILABLE: "Process Available",
            }
            policy_text = policy_map.get(frame_policy, "Stop at Shortest")
            idx = self.frame_policy_combo.findText(policy_text)
            if idx >= 0:
                self.frame_policy_combo.setCurrentIndex(idx)
            
            # Reload attributes
            self.attr_editor.set_attributes(self.state.get_output_attributes())
            
            # Update max frame count
            self._update_max_frame_count()
            
            self._append_log(f"[OK] Project loaded from: {project_path}")
            self._append_log(f"     Loaded {len(self.state.sequences)} sequence(s), "
                            f"{len(self.state.get_output_channels())} output channel(s)")
        except Exception as e:
            self._append_log(f"[ERROR] Failed to load project: {e}")
            QMessageBox.critical(self, "Load Error", f"Failed to load project:\n{e}")