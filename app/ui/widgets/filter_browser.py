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
    QTextEdit,
    QSplitter,
)
from PySide6.QtCore import Qt, Signal

from ...processing import (
    get_all_categories,
    get_filters_by_category,
    ProcessingFilter,
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
        
        # Splitter for tree and description
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Tree widget for filters
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._populate_tree()
        splitter.addWidget(self.tree)
        
        # Description area
        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel("Filter Description:"))
        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setMaximumHeight(120)
        desc_layout.addWidget(self.desc_text)
        
        desc_widget = QWidget()
        desc_widget.setLayout(desc_layout)
        splitter.addWidget(desc_widget)
        
        splitter.setSizes([300, 100])
        layout.addWidget(splitter, 1)
        
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
                filter_item.setData(0, Qt.ItemDataRole.UserRole, filter_instance)
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle tree item selection."""
        filter_obj = item.data(0, Qt.ItemDataRole.UserRole)
        
        if filter_obj is None:
            # Category clicked - clear description
            self.current_filter = None
            self.desc_text.clear()
            self.btn_add.setEnabled(False)
        else:
            # Filter clicked
            self.current_filter = filter_obj
            self._update_description()
            self.btn_add.setEnabled(True)
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle double-click to add filter."""
        filter_obj = item.data(0, Qt.ItemDataRole.UserRole)
        if filter_obj is not None:
            self._on_add_clicked()
    
    def _update_description(self) -> None:
        """Update description text for current filter."""
        if not self.current_filter:
            self.desc_text.clear()
            return
        
        # Build description from filter metadata
        desc = f"<b>{self.current_filter.name}</b>\n"
        
        # List parameters
        if self.current_filter.parameters:
            desc += "\n<b>Parameters:</b>\n"
            for param_name, param in self.current_filter.parameters.items():
                param_type = param.param_type.name
                desc += f"• {param.name}: {param_type}"
                
                if param.min_val is not None and param.max_val is not None:
                    desc += f" ({param.min_val} to {param.max_val})"
                
                if param.description:
                    desc += f" - {param.description}"
                
                desc += "\n"
        
        self.desc_text.setText(desc)
    
    def _on_add_clicked(self) -> None:
        """Handle add button click."""
        if self.current_filter:
            # Create a new instance of the filter (filter classes are instantiable)
            filter_class = type(self.current_filter)
            new_filter = filter_class()  # type: ignore
            self.filter_selected.emit(new_filter)
