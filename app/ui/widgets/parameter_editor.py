"""
Dynamic parameter editor for filter parameters.

Creates appropriate controls (spinboxes, checkboxes, dropdowns)
based on parameter types and constraints.
"""

from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QScrollArea,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal

from ...processing import ProcessingFilter, ParameterType


class ParameterEditor(QWidget):
    """Edit parameters for a selected filter."""
    
    # Signal: emitted when any parameter changes
    parameters_changed = Signal(ProcessingFilter)
    
    def __init__(self):
        super().__init__()
        self.current_filter: Optional[ProcessingFilter] = None
        self.param_controls: Dict[str, Any] = {}
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the parameter editor UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area for parameters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.params_widget = QWidget()
        self.params_layout = QVBoxLayout(self.params_widget)
        self.params_layout.setContentsMargins(5, 5, 5, 5)
        
        scroll.setWidget(self.params_widget)
        layout.addWidget(scroll, 1)
        
        # Clear message
        self.no_filter_label = QLabel("No filter selected")
        self.no_filter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.no_filter_label)
    
    def set_filter(self, filter: Optional[ProcessingFilter]) -> None:
        """Set the filter to edit parameters for."""
        self.current_filter = filter
        self.param_controls.clear()
        
        # Completely clear the layout and all its child widgets
        self._clear_layout(self.params_layout)
        
        if filter is None:
            self.no_filter_label.show()
            return
        
        self.no_filter_label.hide()
        
        # Create controls for each parameter
        if not filter.parameters:
            label = QLabel("(No parameters)")
            self.params_layout.addWidget(label)
            self.params_layout.addStretch()
            return
        
        for param_name, param in filter.parameters.items():
            control = self._create_param_control(param)
            if control:
                self.param_controls[param_name] = control
                
                # Add to layout with label
                param_layout = QHBoxLayout()
                param_layout.addWidget(QLabel(f"{param.name}:"), 0)
                param_layout.addWidget(control, 1)
                self.params_layout.addLayout(param_layout)
        
        # Add stretch at the end to push controls to the top
        self.params_layout.addStretch()
    
    def _clear_layout(self, layout) -> None:
        """Recursively clear all widgets and sublayouts from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                break
            
            # Check if it's a widget
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
                continue
            
            # Check if it's a layout
            sublayout = item.layout()
            if sublayout is not None:
                self._clear_layout(sublayout)
                # Delete the sublayout itself
                sublayout.deleteLater()
    
    def _create_param_control(self, param) -> Optional[QWidget]:
        """Create appropriate control for parameter type."""
        param_type = param.param_type
        
        if param_type == ParameterType.FLOAT:
            spin = QDoubleSpinBox()
            
            if param.min_val is not None:
                spin.setMinimum(param.min_val)
            else:
                spin.setMinimum(-1000000.0)
            
            if param.max_val is not None:
                spin.setMaximum(param.max_val)
            else:
                spin.setMaximum(1000000.0)
            
            if param.value is not None:
                spin.setValue(float(param.value))
            
            spin.setSingleStep(0.1)
            spin.setDecimals(3)
            spin.valueChanged.connect(
                lambda value, pname=param.name: self._on_param_changed(pname, value)
            )
            
            return spin
        
        elif param_type == ParameterType.INT:
            spin = QSpinBox()
            
            if param.min_val is not None:
                spin.setMinimum(int(param.min_val))
            else:
                spin.setMinimum(-1000000)
            
            if param.max_val is not None:
                spin.setMaximum(int(param.max_val))
            else:
                spin.setMaximum(1000000)
            
            if param.value is not None:
                spin.setValue(int(param.value))
            
            spin.valueChanged.connect(
                lambda value, pname=param.name: self._on_param_changed(pname, value)
            )
            
            return spin
        
        elif param_type == ParameterType.BOOL:
            checkbox = QCheckBox()
            
            if param.value is not None:
                checkbox.setChecked(bool(param.value))
            
            checkbox.stateChanged.connect(
                lambda _, pname=param.name: self._on_param_changed(pname, checkbox.isChecked())
            )
            
            return checkbox
        
        elif param_type == ParameterType.CHOICE:
            combo = QComboBox()
            
            if param.options:
                combo.addItems(param.options)
            
            if param.value is not None:
                idx = combo.findText(str(param.value))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            
            combo.currentTextChanged.connect(
                lambda text, pname=param.name: self._on_param_changed(pname, text)
            )
            
            return combo
        
        elif param_type == ParameterType.STRING:
            edit = QLineEdit()
            
            if param.value is not None:
                edit.setText(str(param.value))
            
            edit.textChanged.connect(
                lambda text, pname=param.name: self._on_param_changed(pname, text)
            )
            
            return edit
        
        return None
    
    def _on_param_changed(self, param_name: str, value: Any) -> None:
        """Handle parameter value change."""
        if self.current_filter:
            param = self.current_filter.get_parameter(param_name)
            if param:
                param.value = value
                self.parameters_changed.emit(self.current_filter)
    
    def get_current_filter(self) -> Optional[ProcessingFilter]:
        """Get the currently edited filter."""
        return self.current_filter
