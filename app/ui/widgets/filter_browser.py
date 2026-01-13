"""
Filter browser widget for selecting and adding filters to the pipeline.

Displays available filters organized by category in a tree view.
Allows users to browse and add filters to the active pipeline.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Qt, Signal

from ...processing import (
    get_all_categories,
    get_filters_by_category,
    ProcessingFilter,
    create_filter,
)


class FilterBrowser(QWidget):
    """Browser for available processing filters."""
    
    # Signal: emitted when user wants to add a filter
    filter_selected = Signal(ProcessingFilter)
    
    def __init__(self):
        super().__init__()
        self.current_filter: Optional[ProcessingFilter] = None
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the filter browser UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Top label
        layout.addWidget(QLabel("Available Filters:"))
        
        # Tree widget for filters
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._populate_tree()
        layout.addWidget(self.tree, 1)
        
        # Add button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_add = QPushButton("Add Filter")
        self.btn_add.clicked.connect(self._on_add_clicked)
        self.btn_add.setEnabled(False)
        btn_layout.addWidget(self.btn_add)
        layout.addLayout(btn_layout)
    
    def _populate_tree(self) -> None:
        """Populate tree with filters organized by category."""
        categories = get_all_categories()
        
        for category in sorted(categories):
            category_item = QTreeWidgetItem(self.tree)
            category_item.setText(0, category)
            category_item.setData(0, Qt.ItemDataRole.UserRole, None)  # Not a filter
            
            filters = get_filters_by_category(category)
            for filter_instance in filters:
                filter_item = QTreeWidgetItem(category_item)
                filter_item.setText(0, filter_instance.name)
                # Store filter_id instead of instance, create fresh on demand
                filter_item.setData(0, Qt.ItemDataRole.UserRole, filter_instance.filter_id)
                
                # Set tooltip with filter description
                tooltip = self._build_filter_tooltip(filter_instance)
                filter_item.setToolTip(0, tooltip)
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle tree item selection."""
        filter_id = item.data(0, Qt.ItemDataRole.UserRole)
        
        if filter_id is None:
            # Category clicked
            self.current_filter = None
            self.btn_add.setEnabled(False)
        else:
            # Filter clicked - create fresh instance for display
            self.current_filter = create_filter(filter_id)
            self.btn_add.setEnabled(True)
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle double-click to add filter."""
        filter_id = item.data(0, Qt.ItemDataRole.UserRole)
        if filter_id is not None:
            self._on_add_clicked()
    
    def _build_filter_tooltip(self, filter: ProcessingFilter) -> str:
        """Build tooltip text for a filter."""
        if not filter:
            return ""
        
        # Build tooltip from filter metadata
        tooltip = f"<b>{filter.name}</b>"
        
        # List parameters
        if filter.parameters:
            tooltip += "\n\n<b>Parameters:</b>"
            for param_name, param in filter.parameters.items():
                param_type = param.param_type.name
                tooltip += f"\n• {param.name}: {param_type}"
                
                if param.min_val is not None and param.max_val is not None:
                    tooltip += f" ({param.min_val} to {param.max_val})"
                
                if param.description:
                    tooltip += f" - {param.description}"
        
        return tooltip
    
    def _on_add_clicked(self) -> None:
        """Handle add button click."""
        if self.current_filter:
            # Create a new instance of the filter (filter classes are instantiable)
            filter_class = type(self.current_filter)
            new_filter = filter_class()  # type: ignore
            self.filter_selected.emit(new_filter)
