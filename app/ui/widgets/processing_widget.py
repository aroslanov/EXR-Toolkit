"""
Main processing widget for the Processing tab.

Combines filter browser, pipeline list, and parameter editor
into a complete processing pipeline interface.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QSplitter,
)
from PySide6.QtCore import Qt, Signal, QTimer

from ...processing import ProcessingPipeline
from .filter_browser import FilterBrowser
from .pipeline_list import PipelineList
from .parameter_editor import ParameterEditor


class ProcessingWidget(QWidget):
    """Main widget for the Processing tab."""
    
    # Signal: emitted when processing configuration changes
    config_changed = Signal()
    
    def __init__(self, pipeline: ProcessingPipeline):
        super().__init__()
        self.pipeline = pipeline
        self.input_color_space: Optional[str] = None  # Hint for color conversion filter defaults
        self._build_ui()
        self._connect_signals()
    
    def _build_ui(self) -> None:
        """Build the processing widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Enable/disable checkbox
        header_layout = QHBoxLayout()
        self.enable_checkbox = QCheckBox("Enable Processing Pipeline")
        self.enable_checkbox.setChecked(self.pipeline.enabled)
        self.enable_checkbox.stateChanged.connect(self._on_enable_changed)
        header_layout.addWidget(self.enable_checkbox)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Main splitter: left side (filter browser) and right side (pipeline + editor)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Filter browser
        self.filter_browser = FilterBrowser()
        self.filter_browser.filter_selected.connect(self._on_filter_selected)
        self.main_splitter.addWidget(self.filter_browser)
        
        # Right side: vertical splitter (pipeline list on top, parameter editor on bottom)
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Pipeline list
        self.pipeline_list = PipelineList(self.pipeline)
        self.pipeline_list.filter_removed.connect(self._on_filter_removed)
        self.pipeline_list.filter_moved.connect(self._on_filter_moved)
        self.pipeline_list.filter_toggled.connect(self._on_filter_toggled)
        right_splitter.addWidget(self.pipeline_list)
        
        # Parameter editor
        self.param_editor = ParameterEditor()
        self.param_editor.parameters_changed.connect(self._on_parameters_changed)
        right_splitter.addWidget(self.param_editor)
        
        right_splitter.setSizes([250, 200])
        self.main_splitter.addWidget(right_splitter)
        
        # Default ratio: left 45%, right 55% (user remains free to resize).
        self.main_splitter.setStretchFactor(0, 45)
        self.main_splitter.setStretchFactor(1, 55)
        layout.addWidget(self.main_splitter, 1)

        # Apply initial pixel sizes once the widget has a real width.
        QTimer.singleShot(0, self._apply_main_splitter_default_sizes)

    def _apply_main_splitter_default_sizes(self) -> None:
        total_width = self.main_splitter.size().width()
        if total_width <= 0:
            total_width = max(self.size().width(), 800)

        left = int(total_width * 0.45)
        right = max(total_width - left, 1)
        self.main_splitter.setSizes([left, right])
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # When user selects a filter in pipeline list, show its parameters
        self.pipeline_list.list.itemClicked.connect(self._on_pipeline_item_clicked)
    
    def set_pipeline(self, pipeline: ProcessingPipeline) -> None:
        """Update the pipeline reference."""
        self.pipeline = pipeline
        self.enable_checkbox.setChecked(pipeline.enabled)
        self.pipeline_list.set_pipeline(pipeline)
        self.param_editor.set_filter(None)
    
    def set_input_color_space(self, color_space: Optional[str]) -> None:
        """
        Set the input footage color space hint.
        Used to default the ColorSpaceConversionFilter's 'from_space' parameter.
        """
        self.input_color_space = color_space
    
    def _on_enable_changed(self, state: int) -> None:
        """Handle enable/disable checkbox."""
        self.pipeline.enabled = self.enable_checkbox.isChecked()
        self.config_changed.emit()
    
    def _on_filter_selected(self, filter) -> None:
        """Handle filter selection from browser."""
        # Set default color space for color conversion filter if input is known
        from ...processing import ColorSpaceConversionFilter
        if isinstance(filter, ColorSpaceConversionFilter) and self.input_color_space:
            filter.set_parameter("from_space", self.input_color_space)
        
        # Add filter to pipeline
        self.pipeline_list.add_filter(filter)
        
        # Select it in the list and show its parameters
        last_idx = len(self.pipeline.filters) - 1
        self.pipeline_list.list.setCurrentRow(last_idx)
        self._show_filter_params(filter)
        
        self.config_changed.emit()
    
    def _on_pipeline_item_clicked(self) -> None:
        """Handle pipeline list item click."""
        current_row = self.pipeline_list.list.currentRow()
        if 0 <= current_row < len(self.pipeline.filters):
            filter = self.pipeline.filters[current_row]
            self._show_filter_params(filter)
    
    def _show_filter_params(self, filter) -> None:
        """Show parameters for a filter in the editor."""
        self.param_editor.set_filter(filter)
    
    def _on_filter_removed(self, index: int) -> None:
        """Handle filter removal."""
        self.param_editor.set_filter(None)
        self.config_changed.emit()
    
    def _on_filter_moved(self, from_idx: int, to_idx: int) -> None:
        """Handle filter reordering."""
        self.config_changed.emit()
    
    def _on_filter_toggled(self, index: int) -> None:
        """Handle filter enable/disable."""
        self.config_changed.emit()
    
    def _on_parameters_changed(self, filter) -> None:
        """Handle parameter value changes."""
        self.config_changed.emit()
    
    def get_pipeline(self) -> ProcessingPipeline:
        """Get the current pipeline."""
        return self.pipeline
