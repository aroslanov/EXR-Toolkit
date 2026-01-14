"""
Qt models for EXR Toolkit UI.

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

    def clear_sequences(self) -> None:
        """Clear all sequences."""
        self.beginResetModel()
        self.sequences.clear()
        self.endResetModel()

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
            # Include pattern filename in display
            filename = str(seq.pattern.pattern)
            return f"{seq.display_name} | {filename}"

        if role == Qt.ItemDataRole.ToolTipRole:
            return self._format_sequence_tooltip(seq)

        if role == Qt.ItemDataRole.UserRole:
            return seq.id

        return None

    def _format_sequence_tooltip(self, seq: SequenceSpec) -> str:
        """Format sequence information for tooltip display."""
        lines = []
        lines.append(f"<b>{seq.display_name}</b>")
        lines.append("")
        
        # Frame information
        if seq.frames:
            frame_count = len(seq.frames)
            min_frame = min(seq.frames)
            max_frame = max(seq.frames)
            lines.append(f"<b>Frames:</b> {frame_count} ({min_frame} - {max_frame})")
        
        # Probe information (size, bit depth, compression, etc.)
        if seq.static_probe and seq.static_probe.main_subimage:
            probe = seq.static_probe.main_subimage
            spec = probe.spec
            
            # Image dimensions
            lines.append(f"<b>Resolution:</b> {spec.width} x {spec.height}")
            
            # Pixel format / bit depth
            if spec.format and spec.format != "unknown":
                lines.append(f"<b>Format:</b> {spec.format}")
            
            # Channels
            if spec.nchannels > 0:
                lines.append(f"<b>Channels:</b> {spec.nchannels}")
            
            # Tile information
            if spec.tile_width > 0 and spec.tile_height > 0:
                lines.append(f"<b>Tiling:</b> {spec.tile_width} x {spec.tile_height}")
            
            # Compression attribute
            compression_attr = probe.attributes.get_by_name("compression")
            if compression_attr:
                lines.append(f"<b>Compression:</b> {compression_attr.value}")
            
            # Other useful attributes
            pixel_aspect = probe.attributes.get_by_name("pixelAspectRatio")
            if pixel_aspect:
                lines.append(f"<b>Pixel Aspect:</b> {pixel_aspect.value}")
            
            display_window = probe.attributes.get_by_name("displayWindow")
            if display_window:
                lines.append(f"<b>Display Window:</b> {display_window.value}")
        else:
            lines.append("<i>No probe data available</i>")
            lines.append("<i>Click 'Load Sequence' to extract metadata</i>")
        
        return "<br>".join(lines)


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

    def clear_channels(self) -> None:
        """Clear all channels."""
        self.beginResetModel()
        self.channels.clear()
        self.endResetModel()

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


class AttributeListModel(QAbstractListModel):
    """Model for a read-only attribute list (for selection)."""

    def __init__(self):
        super().__init__()
        self.attributes: List[AttributeSpec] = []

    def set_attributes(self, attributes: List[AttributeSpec]) -> None:
        """Replace attributes and refresh view."""
        self.beginResetModel()
        self.attributes = attributes
        self.endResetModel()

    def get_attribute(self, index: int) -> Optional[AttributeSpec]:
        """Get attribute at index."""
        if 0 <= index < len(self.attributes):
            return self.attributes[index]
        return None

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> int:
        return len(self.attributes)

    def data(
        self,
        index: Union[QModelIndex, QPersistentModelIndex],
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None

        attr = self.attributes[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return f"{attr.name}: {attr.value}"

        if role == Qt.ItemDataRole.UserRole:
            return attr

        return None


class AttributeTableModel(QAbstractTableModel):
    """Model for attribute table (Name, Type, Value)."""

    COLUMNS = ["Name", "Type", "Value"]

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

        if role == Qt.ItemDataRole.UserRole:
            return attr

        return None

    def setData(
        self,
        index: Union[QModelIndex, QPersistentModelIndex],
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Editing is disabled - only selection allowed."""
        return False

    def flags(self, index: Union[QModelIndex, QPersistentModelIndex]):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        default_flags = super().flags(index)

        # Only allow selection, no editing
        return default_flags & ~Qt.ItemFlag.ItemIsEditable
