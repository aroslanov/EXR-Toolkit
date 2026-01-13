"""
Pipeline list widget for displaying and managing active filters.

Shows currently applied filters in order, with controls for
reordering, disabling, and removing filters.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Qt, Signal

from ...processing import ProcessingPipeline, ProcessingFilter


class PipelineList(QWidget):
    """Display and manage filters in the processing pipeline."""
    
    # Signals
    filter_removed = Signal(int)  # index
    filter_moved = Signal(int, int)  # from_index, to_index
    filter_toggled = Signal(int)  # index (filter enabled/disabled)
    
    def __init__(self, pipeline: ProcessingPipeline):
        super().__init__()
        self.pipeline = pipeline
        self._build_ui()
        self._refresh_list()
    
    def _build_ui(self) -> None:
        """Build the pipeline list UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        layout.addWidget(QLabel("Active Filters (applied in order):"))
        
        # List widget
        self.list = QListWidget()
        self.list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list, 1)
        
        # Control buttons
        # Use a grid instead of a single horizontal row to avoid a large minimum width
        # (a QHBoxLayout's minimum width becomes the sum of all button minimum widths).
        btn_layout = QGridLayout()

        self.btn_up = QPushButton("↑ Move Up")
        self.btn_up.clicked.connect(self._on_move_up)
        self.btn_up.setEnabled(False)
        btn_layout.addWidget(self.btn_up, 0, 0)

        self.btn_down = QPushButton("↓ Move Down")
        self.btn_down.clicked.connect(self._on_move_down)
        self.btn_down.setEnabled(False)
        btn_layout.addWidget(self.btn_down, 0, 1)

        self.btn_toggle = QPushButton("☑ Toggle")
        self.btn_toggle.clicked.connect(self._on_toggle_enabled)
        self.btn_toggle.setEnabled(False)
        btn_layout.addWidget(self.btn_toggle, 1, 0)

        self.btn_remove = QPushButton("✕ Remove")
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_remove.setEnabled(False)
        btn_layout.addWidget(self.btn_remove, 1, 1)

        btn_layout.setColumnStretch(0, 1)
        btn_layout.setColumnStretch(1, 1)
        layout.addLayout(btn_layout)
    
    def set_pipeline(self, pipeline: ProcessingPipeline) -> None:
        """Update the pipeline reference."""
        self.pipeline = pipeline
        self._refresh_list()
    
    def add_filter(self, filter: ProcessingFilter) -> None:
        """Add a filter to the pipeline and refresh display."""
        self.pipeline.add_filter(filter)
        self._refresh_list()
    
    def _refresh_list(self) -> None:
        """Refresh the list display from pipeline."""
        self.list.clear()
        
        for i, filter in enumerate(self.pipeline.filters):
            # Create item with checkbox and filter name
            enabled_icon = "☑" if filter.enabled else "☐"
            item_text = f"{enabled_icon} {i+1}. {filter.name}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, i)  # Store index
            
            # Set tooltip with filter description
            tooltip = self._build_filter_tooltip(filter)
            item.setToolTip(tooltip)
            
            self.list.addItem(item)
    
    def _build_filter_tooltip(self, filter) -> str:
        """Build tooltip text for a filter."""
        if not filter:
            return ""
        
        # Build tooltip from filter metadata
        tooltip = f"<b>{filter.name}</b>"
        
        # List parameters
        if hasattr(filter, 'parameters') and filter.parameters:
            tooltip += "\n\n<b>Parameters:</b>"
            for param_name, param in filter.parameters.items():
                param_type = param.param_type.name
                tooltip += f"\n• {param.name}: {param_type}"
                
                if param.min_val is not None and param.max_val is not None:
                    tooltip += f" ({param.min_val} to {param.max_val})"
                
                if param.description:
                    tooltip += f" - {param.description}"
        
        return tooltip
    
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle filter selection."""
        # Find which filter is selected
        index = self.list.row(item)
        
        # Enable/disable buttons based on position
        can_move_up = index > 0
        can_move_down = index < len(self.pipeline.filters) - 1
        
        self.btn_up.setEnabled(can_move_up)
        self.btn_down.setEnabled(can_move_down)
        self.btn_toggle.setEnabled(True)
        self.btn_remove.setEnabled(True)
    
    def _on_move_up(self) -> None:
        """Move selected filter up."""
        current_row = self.list.currentRow()
        if current_row > 0:
            self.pipeline.move_filter(current_row, current_row - 1)
            self._refresh_list()
            self.list.setCurrentRow(current_row - 1)
            self.filter_moved.emit(current_row, current_row - 1)
    
    def _on_move_down(self) -> None:
        """Move selected filter down."""
        current_row = self.list.currentRow()
        if current_row < len(self.pipeline.filters) - 1:
            self.pipeline.move_filter(current_row, current_row + 1)
            self._refresh_list()
            self.list.setCurrentRow(current_row + 1)
            self.filter_moved.emit(current_row, current_row + 1)
    
    def _on_toggle_enabled(self) -> None:
        """Toggle enabled state of selected filter."""
        current_row = self.list.currentRow()
        if 0 <= current_row < len(self.pipeline.filters):
            filter = self.pipeline.filters[current_row]
            filter.enabled = not filter.enabled
            self._refresh_list()
            self.list.setCurrentRow(current_row)
            self.filter_toggled.emit(current_row)
    
    def _on_remove(self) -> None:
        """Remove selected filter."""
        current_row = self.list.currentRow()
        if current_row >= 0:
            self.pipeline.remove_filter(current_row)
            self._refresh_list()
            self.filter_removed.emit(current_row)
