"""
Attribute editor widget for EXR metadata.

Displays and edits attributes in a table with type-aware editors.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QPushButton,
    QHeaderView,
    QDialog,
    QLabel,
    QLineEdit,
    QComboBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal

from ...core import AttributeSpec, AttributeSet, AttributeSource
from ..models import AttributeTableModel


class AttributeEditor(QWidget):
    """Widget for editing output attributes."""

    # Signal emitted when attributes change
    attributes_changed = Signal(AttributeSet)

    def __init__(self):
        super().__init__()
        self.model = AttributeTableModel()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI."""
        layout = QVBoxLayout(self)

        # Table view
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_add = QPushButton("Add Attribute")
        btn_add.clicked.connect(self._on_add_attribute)
        btn_layout.addWidget(btn_add)

        btn_remove = QPushButton("Remove")
        btn_remove.clicked.connect(self._on_remove_attribute)
        btn_layout.addWidget(btn_remove)

        btn_import = QPushButton("Import from Source")
        btn_import.clicked.connect(self._on_import_from_source)
        btn_layout.addWidget(btn_import)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_attributes(self, attrs: AttributeSet) -> None:
        """Set the attribute list to display."""
        self.model.set_attributes(attrs.attributes)

    def get_attributes(self) -> AttributeSet:
        """Get current attributes from the model."""
        return AttributeSet(attributes=self.model.attributes)

    def _on_add_attribute(self) -> None:
        """Handle 'Add Attribute' button."""
        dialog = AddAttributeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            attr = dialog.get_attribute()
            self.model.add_attribute(attr)
            self.attributes_changed.emit(self.get_attributes())

    def _on_remove_attribute(self) -> None:
        """Handle 'Remove' button."""
        current = self.table.currentIndex()
        if current.isValid():
            self.model.remove_at(current.row())
            self.attributes_changed.emit(self.get_attributes())

    def _on_import_from_source(self) -> None:
        """Handle 'Import from Source' button."""
        # This is a placeholder; actual implementation depends on MainWindow
        # providing access to loaded sequences
        pass


class AddAttributeDialog(QDialog):
    """Dialog for adding a new attribute."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Attribute")
        self.setGeometry(100, 100, 400, 200)

        layout = QVBoxLayout(self)

        # Name
        layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        # Type
        layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "string",
            "int",
            "float",
            "unknown",
        ])
        layout.addWidget(self.type_combo)

        # Value
        layout.addWidget(QLabel("Value:"))
        self.value_edit = QLineEdit()
        layout.addWidget(self.value_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def get_attribute(self) -> AttributeSpec:
        """Get the configured attribute."""
        return AttributeSpec(
            name=self.name_edit.text(),
            oiio_type=self.type_combo.currentText(),
            value=self.value_edit.text(),
            source=AttributeSource.CUSTOM,
            editable=True,
        )
