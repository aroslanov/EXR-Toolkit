"""
Qt models for EXR Channel Recombiner UI.

Implements MVC pattern for:
- Sequence list
- Channel list (for selected sequence)
- Output channel list
- Output attribute table
"""

from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QAbstractTableModel, QPersistentModelIndex
from typing import Any, List, Optional, Union

from ...core import SequenceSpec, ChannelSpec, OutputChannel, AttributeSpec


class SequenceListModel(QAbstractListModel):
    """Model for the sequence list."""

    def __init__(self):
        super().__init__()
        self.sequences: List[SequenceSpec] = []

    def set_sequences(self, sequences: List[SequenceSpec]) -> None:
        """Replace sequences entirely and refresh view."""
        self.beginResetModel()
        self.sequences = sequences
        self.endResetModel()

    def add_sequence(self, seq: SequenceSpec) -> None:
        """Add a single sequence."""
        self.beginInsertRows(QModelIndex(), len(self.sequences), len(self.sequences))
        self.sequences.append(seq)
        self.endInsertRows()

    def remove_at(self, index: int) -> bool:
        """Remove sequence at index."""
        if 0 <= index < len(self.sequences):
            self.beginRemoveRows(QModelIndex(), index, index)
            del self.sequences[index]
            self.endRemoveRows()
            return True
        return False

    def get_sequence(self, index: int) -> Optional[SequenceSpec]:
        """Get sequence at index."""
        if 0 <= index < len(self.sequences):
            return self.sequences[index]
        return None

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        return len(self.sequences)

    def data(
        self,
        index: Union[QModelIndex, QPersistentModelIndex],
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None

        seq = self.sequences[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return f"{seq.display_name} ({len(seq.frames)} frames)"

        if role == Qt.ItemDataRole.UserRole:
            return seq.id

        return None


class ChannelListModel(QAbstractListModel):
    """Model for channels of a selected sequence."""

    def __init__(self):
        super().__init__()
        self.channels: List[ChannelSpec] = []

    def set_channels(self, channels: List[ChannelSpec]) -> None:
        """Replace channels and refresh view."""
        self.beginResetModel()
        self.channels = channels
        self.endResetModel()

    def get_channel(self, index: int) -> Optional[ChannelSpec]:
        """Get channel at index."""
        if 0 <= index < len(self.channels):
            return self.channels[index]
        return None

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        return len(self.channels)

    def data(
        self,
        index: Union[QModelIndex, QPersistentModelIndex],
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None

        ch = self.channels[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return f"{ch.name} ({ch.format.oiio_type})"

        if role == Qt.ItemDataRole.UserRole:
            return ch.name

        return None


class OutputChannelListModel(QAbstractListModel):
    """Model for the output channel list."""

    def __init__(self):
        super().__init__()
        self.channels: List[OutputChannel] = []

    def set_channels(self, channels: List[OutputChannel]) -> None:
        """Replace channels and refresh view."""
        self.beginResetModel()
        self.channels = channels
        self.endResetModel()

    def add_channel(self, channel: OutputChannel) -> None:
        """Add a single output channel."""
        self.beginInsertRows(QModelIndex(), len(self.channels), len(self.channels))
        self.channels.append(channel)
        self.endInsertRows()

    def remove_at(self, index: int) -> bool:
        """Remove channel at index."""
        if 0 <= index < len(self.channels):
            self.beginRemoveRows(QModelIndex(), index, index)
            del self.channels[index]
            self.endRemoveRows()
            return True
        return False

    def update_at(self, index: int, channel: OutputChannel) -> bool:
        """Update channel at index."""
        if 0 <= index < len(self.channels):
            self.channels[index] = channel
            self.dataChanged.emit(self.index(index), self.index(index))
            return True
        return False

    def get_channel(self, index: int) -> Optional[OutputChannel]:
        """Get channel at index."""
        if 0 <= index < len(self.channels):
            return self.channels[index]
        return None

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        return len(self.channels)

    def data(
        self,
        index: Union[QModelIndex, QPersistentModelIndex],
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None

        ch = self.channels[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return f"{ch.output_name} <- {ch.source.channel_name} ({ch.source.sequence_id})"

        if role == Qt.ItemDataRole.UserRole:
            return ch.output_name

        return None


class AttributeTableModel(QAbstractTableModel):
    """Model for attribute table (Name, Type, Value, Source, Enabled)."""

    COLUMNS = ["Name", "Type", "Value", "Source", "Enabled"]

    def __init__(self):
        super().__init__()
        self.attributes: List[AttributeSpec] = []

    def set_attributes(self, attributes: List[AttributeSpec]) -> None:
        """Replace attributes and refresh view."""
        self.beginResetModel()
        self.attributes = attributes
        self.endResetModel()

    def add_attribute(self, attr: AttributeSpec) -> None:
        """Add attribute (or update if name exists)."""
        for i, existing in enumerate(self.attributes):
            if existing.name == attr.name:
                self.attributes[i] = attr
                self.dataChanged.emit(self.index(i, 0), self.index(i, len(self.COLUMNS) - 1))
                return

        self.beginInsertRows(QModelIndex(), len(self.attributes), len(self.attributes))
        self.attributes.append(attr)
        self.endInsertRows()

    def remove_at(self, index: int) -> bool:
        """Remove attribute at index."""
        if 0 <= index < len(self.attributes):
            self.beginRemoveRows(QModelIndex(), index, index)
            del self.attributes[index]
            self.endRemoveRows()
            return True
        return False

    def get_attribute(self, index: int) -> Optional[AttributeSpec]:
        """Get attribute at index."""
        if 0 <= index < len(self.attributes):
            return self.attributes[index]
        return None

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        return len(self.attributes)

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
        return None

    def data(
        self,
        index: Union[QModelIndex, QPersistentModelIndex],
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None

        attr = self.attributes[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return attr.name
            elif col == 1:
                return attr.oiio_type
            elif col == 2:
                return str(attr.value)
            elif col == 3:
                return attr.source.name
            elif col == 4:
                return "✓" if attr.editable else "✗"

        if role == Qt.ItemDataRole.UserRole:
            return attr

        return None

    def setData(
        self,
        index: Union[QModelIndex, QPersistentModelIndex],
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Support editing (basic implementation)."""
        if not index.isValid():
            return False

        if role != Qt.ItemDataRole.EditRole:
            return False

        attr = self.attributes[index.row()]
        col = index.column()

        if col == 0:
            attr.name = str(value)
        elif col == 2:
            attr.value = value
        else:
            return False

        self.dataChanged.emit(index, index)
        return True

    def flags(self, index: Union[QModelIndex, QPersistentModelIndex]):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        attr = self.attributes[index.row()]
        col = index.column()

        default_flags = super().flags(index)

        # Name and Value columns are editable
        if col in [0, 2]:
            return default_flags | Qt.ItemFlag.ItemIsEditable

        return default_flags
