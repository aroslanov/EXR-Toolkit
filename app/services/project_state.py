"""
Project state management.

Central in-memory store for:
- Loaded sequences
- Output channel specification
- Export settings
- Attribute merging and conflict resolution
"""

from typing import Optional, List
from pathlib import Path

from ..core import (
    SequenceSpec,
    ExportSpec,
    OutputChannel,
    AttributeSet,
    AttributeSpec,
    AttributeSource,
    ChannelSourceRef,
)


class ProjectState:
    """Central state management for the application."""

    def __init__(self):
        self.sequences: dict[str, SequenceSpec] = {}
        self.export_spec = ExportSpec(
            output_dir="",
            filename_pattern="output.%04d.exr",
        )

    # ========== Sequence Management ==========

    def add_sequence(self, seq: SequenceSpec) -> None:
        """Add a loaded sequence to the project."""
        self.sequences[seq.id] = seq

    def remove_sequence(self, seq_id: str) -> bool:
        """Remove a sequence by ID. Returns True if it existed."""
        if seq_id in self.sequences:
            del self.sequences[seq_id]
            return True
        return False

    def get_sequence(self, seq_id: str) -> Optional[SequenceSpec]:
        """Get a sequence by ID."""
        return self.sequences.get(seq_id)

    def list_sequences(self) -> List[SequenceSpec]:
        """List all loaded sequences."""
        return list(self.sequences.values())

    # ========== Output Channel Management ==========

    def add_output_channel(self, output_channel: OutputChannel) -> None:
        """Add a channel to the output specification."""
        self.export_spec.output_channels.append(output_channel)

    def remove_output_channel(self, index: int) -> bool:
        """Remove an output channel by index."""
        if 0 <= index < len(self.export_spec.output_channels):
            del self.export_spec.output_channels[index]
            return True
        return False

    def update_output_channel(self, index: int, channel: OutputChannel) -> bool:
        """Update an output channel by index."""
        if 0 <= index < len(self.export_spec.output_channels):
            self.export_spec.output_channels[index] = channel
            return True
        return False

    def get_output_channels(self) -> List[OutputChannel]:
        """Get all output channels."""
        return self.export_spec.output_channels

    def clear_output_channels(self) -> None:
        """Clear all output channels."""
        self.export_spec.output_channels.clear()

    # ========== Export Settings ==========

    def set_output_dir(self, path: str) -> None:
        """Set output directory."""
        self.export_spec.output_dir = path

    def get_output_dir(self) -> str:
        """Get output directory."""
        return self.export_spec.output_dir

    def set_filename_pattern(self, pattern: str) -> None:
        """Set filename pattern."""
        self.export_spec.filename_pattern = pattern

    def get_filename_pattern(self) -> str:
        """Get filename pattern."""
        return self.export_spec.filename_pattern

    def set_compression(self, compression: str) -> None:
        """Set EXR compression method."""
        self.export_spec.compression = compression

    def get_compression(self) -> str:
        """Get current compression."""
        return self.export_spec.compression

    # ========== Attribute Management ==========

    def set_output_attributes(self, attrs: AttributeSet) -> None:
        """Replace output attributes entirely."""
        self.export_spec.output_attributes = attrs

    def get_output_attributes(self) -> AttributeSet:
        """Get output attributes."""
        return self.export_spec.output_attributes

    def add_output_attribute(self, attr: AttributeSpec) -> None:
        """Add or update an output attribute."""
        self.export_spec.output_attributes.add_or_update(attr)

    def import_attributes_from_sequence(
        self, seq_id: str, subimage_index: int = 0, merge: bool = False
    ) -> None:
        """
        Import attributes from a sequence's probe.

        If merge=False: replace output attributes.
        If merge=True: add attributes not already present.
        """
        seq = self.get_sequence(seq_id)
        if not seq or not seq.static_probe:
            return

        probe = seq.static_probe
        if subimage_index >= len(probe.subimages):
            return

        src_attrs = probe.subimages[subimage_index].attributes

        if not merge:
            # Replace with imported attributes
            new_attrs = AttributeSet(attributes=[
                AttributeSpec(
                    name=attr.name,
                    oiio_type=attr.oiio_type,
                    value=attr.value,
                    source=AttributeSource.INPUT_SEQ,
                    editable=attr.editable,
                )
                for attr in src_attrs.attributes
            ])
            self.set_output_attributes(new_attrs)
        else:
            # Merge: add only new attributes
            for attr in src_attrs.attributes:
                if self.export_spec.output_attributes.get_by_name(attr.name) is None:
                    new_attr = AttributeSpec(
                        name=attr.name,
                        oiio_type=attr.oiio_type,
                        value=attr.value,
                        source=AttributeSource.INPUT_SEQ,
                        editable=attr.editable,
                    )
                    self.add_output_attribute(new_attr)

    # ========== Validation Context ==========

    def can_export(self) -> tuple[bool, List[str]]:
        """
        Quick check: can we attempt export?
        Returns (can_export, issues_list).
        For detailed validation, use ValidationEngine.
        """
        issues = []

        if not self.export_spec.output_channels:
            issues.append("No output channels defined.")

        if not self.export_spec.output_dir:
            issues.append("Output directory not set.")

        return len(issues) == 0, issues

    def get_export_spec(self) -> ExportSpec:
        """Get the full export specification."""
        return self.export_spec
