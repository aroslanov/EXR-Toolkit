"""
Filter browser widget for selecting and adding filters to the pipeline.

Displays available filters organized by category in a tree view.
Allows users to browse and add filters to the active pipeline.
"""

# Import Optional type hint for optional parameters
from typing import Optional
# Import all necessary PySide6 Qt widgets for UI construction
from PySide6.QtWidgets import (
    QWidget,  # Base widget class
    QVBoxLayout,  # Vertical layout manager
    QHBoxLayout,  # Horizontal layout manager
    QTreeWidget,  # Tree view widget for hierarchical display
    QTreeWidgetItem,  # Individual item in tree widget
    QPushButton,  # Clickable button widget
    QLabel,  # Text label widget
)
# Import Qt core signals and enums
from PySide6.QtCore import Qt, Signal

# Import filter management functions and classes
from ...processing import (
    get_all_categories,  # Get all available filter categories
    get_filters_by_category,  # Get filters for a specific category
    ProcessingFilter,  # Base filter class
    create_filter,  # Factory function to create filters by ID
)


# Define FilterBrowser class that inherits from QWidget (base UI element)
class FilterBrowser(QWidget):
    """Browser for available processing filters."""
    
    # Qt Signal emitted when user selects a filter to add to pipeline
    filter_selected = Signal(ProcessingFilter)
    
    # Constructor - initializes the filter browser widget
    def __init__(self):
        # Call parent class constructor
        super().__init__()
        # Initialize variable to track currently selected filter (None if category selected)
        self.current_filter: Optional[ProcessingFilter] = None
        # Build the user interface components
        self._build_ui()
    
    # Private method that constructs the entire UI layout
    def _build_ui(self) -> None:
        """Build the filter browser UI."""
        # Create main vertical layout for widget
        layout = QVBoxLayout(self)
        # Remove spacing around the layout borders for compact appearance
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add header label to indicate this is a filter list
        layout.addWidget(QLabel("Available Filters:"))
        
        # Create tree widget for hierarchical category/filter display
        self.tree = QTreeWidget()
        # Hide the default column header for cleaner appearance
        self.tree.setHeaderHidden(True)
        # Connect single-click event to filter selection handler
        self.tree.itemClicked.connect(self._on_item_clicked)
        # Connect double-click event to add filter handler
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        # Populate tree with all available filters organized by category
        self._populate_tree()
        # Add tree widget to layout with stretch factor 1 (takes available space)
        layout.addWidget(self.tree, 1)
        
        # Create horizontal layout for button area at bottom
        btn_layout = QHBoxLayout()
        # Add flexible spacing to push button to the right
        btn_layout.addStretch()
        # Create "Add Filter" button
        self.btn_add = QPushButton("Add Filter")
        # Connect button click event to add filter handler
        self.btn_add.clicked.connect(self._on_add_clicked)
        # Initially disable button until a filter is selected
        self.btn_add.setEnabled(False)
        # Add button to horizontal layout
        btn_layout.addWidget(self.btn_add)
        # Add button layout to main vertical layout
        layout.addLayout(btn_layout)
    
    # Private method that populates tree widget with filters grouped by category
    def _populate_tree(self) -> None:
        """Populate tree with filters organized by category."""
        # Get list of all filter categories in preferred order
        categories = get_all_categories()
        
        # Iterate through each category in sorted order
        for category in sorted(categories):
            # Create a new tree item representing this category at root level
            category_item = QTreeWidgetItem(self.tree)
            # Set the display text to the category name
            category_item.setText(0, category)
            # Store None as data to indicate this item is a category, not a filter
            category_item.setData(0, Qt.ItemDataRole.UserRole, None)  # Not a filter
            
            # Get all filters that belong to this category
            filters = get_filters_by_category(category)
            # Iterate through each filter in the category
            for filter_instance in filters:
                # Skip filters marked as hidden (incomplete or not useful)
                if filter_instance.hidden:
                    continue
                    
                # Create a new tree item as a child of the category item
                filter_item = QTreeWidgetItem(category_item)
                # Set display text to the filter's user-friendly name
                filter_item.setText(0, filter_instance.name)
                # Store filter_id in item data for later instantiation
                # Store filter_id instead of instance, create fresh on demand
                filter_item.setData(0, Qt.ItemDataRole.UserRole, filter_instance.filter_id)
                
                # Build and set a detailed tooltip showing filter information
                # Set tooltip with filter description
                tooltip = self._build_filter_tooltip(filter_instance)
                # Attach tooltip to item for display on mouse hover
                filter_item.setToolTip(0, tooltip)
    
    # Private method called when user clicks an item in the tree
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle tree item selection."""
        # Extract filter_id from clicked item (None if category, string if filter)
        filter_id = item.data(0, Qt.ItemDataRole.UserRole)
        
        # Check if clicked item is a category (has no filter_id)
        if filter_id is None:
            # Category clicked - clear current filter selection
            self.current_filter = None
            # Disable add button since no actual filter is selected
            self.btn_add.setEnabled(False)
        else:
            # Filter clicked - create fresh instance for display
            # Instantiate a new filter object using the stored filter_id
            self.current_filter = create_filter(filter_id)
            # Enable add button now that a filter is selected
            self.btn_add.setEnabled(True)
    
    # Private method called when user double-clicks an item in the tree
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle double-click to add filter."""
        # Extract filter_id from double-clicked item
        filter_id = item.data(0, Qt.ItemDataRole.UserRole)
        # Check if a filter was clicked (not a category)
        if filter_id is not None:
            # Trigger add filter action as if user clicked the button
            self._on_add_clicked()
    
    # Private method that creates a rich tooltip string for a filter
    def _build_filter_tooltip(self, filter: ProcessingFilter) -> str:
        """Build tooltip text for a filter."""
        # Return empty string if filter object is invalid
        if not filter:
            return ""
        
        # Start tooltip with filter name in bold HTML formatting
        # Build tooltip from filter metadata
        tooltip = f"<b>{filter.name}</b>"
        
        # Check if filter has any parameters to display
        # List parameters
        if filter.parameters:
            # Add parameters section header to tooltip
            tooltip += "\n\n<b>Parameters:</b>"
            # Iterate through each parameter in the filter
            for param_name, param in filter.parameters.items():
                # Get the parameter type name (FLOAT, INT, CHOICE, etc.)
                param_type = param.param_type.name
                # Add parameter name and type to tooltip
                tooltip += f"\n• {param.name}: {param_type}"
                
                # Check if parameter has min/max value constraints
                if param.min_val is not None and param.max_val is not None:
                    # Append valid range to tooltip
                    tooltip += f" ({param.min_val} to {param.max_val})"
                
                # Check if parameter has a description
                if param.description:
                    # Append parameter description to tooltip
                    tooltip += f" - {param.description}"
        
        # Return the fully formatted tooltip string
        return tooltip
    
    # Private method called when user clicks the "Add Filter" button
    def _on_add_clicked(self) -> None:
        """Handle add button click."""
        # Check if a filter is currently selected
        if self.current_filter:
            # Get the class/type of the currently selected filter
            # Create a new instance of the filter (filter classes are instantiable)
            filter_class = type(self.current_filter)
            # Instantiate a fresh copy of the selected filter class
            new_filter = filter_class()  # type: ignore
            # Emit signal to notify parent widgets that filter was selected
            self.filter_selected.emit(new_filter)
