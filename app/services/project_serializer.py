"""
Project serialization and deserialization.

Handles saving and loading of project state to/from JSON format.
Designed to be easily extensible for future features.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core import (
    SequenceSpec,
    SequencePathPattern,
    OutputChannel,
    ChannelSourceRef,
    AttributeSpec,
    AttributeSet,
    AttributeSource,
    FrameRangePolicy,
    ExportSpec,
)
from .project_state import ProjectState


class ProjectSerializer:
    """
    Serializes and deserializes ProjectState to/from JSON.
    
    Format is extensible:
    - Version field allows backward compatibility
    - Each major component (sequences, export_spec) can be extended
    - New attributes can be added without breaking old files
    """

    # Format version for future compatibility
    FORMAT_VERSION = "1.0"

    @staticmethod
    def serialize(state: ProjectState) -> Dict[str, Any]:
        """
        Convert ProjectState to a serializable dictionary.
        
        Gathers all project data in an extensible format.
        """
        return {
            "format_version": ProjectSerializer.FORMAT_VERSION,
            "sequences": ProjectSerializer._serialize_sequences(state.sequences),
            "export_spec": ProjectSerializer._serialize_export_spec(state.export_spec),
        }

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> ProjectState:
        """
        Convert a dictionary back to ProjectState.
        
        Applies all project data with validation.
        """
        # Version check for future compatibility
        version = data.get("format_version", "1.0")
        if version != ProjectSerializer.FORMAT_VERSION:
            raise ValueError(
                f"Unsupported project format version: {version}. "
                f"Expected {ProjectSerializer.FORMAT_VERSION}"
            )

        state = ProjectState()

        # Restore sequences
        sequences_data = data.get("sequences", {})
        for seq_id, seq_dict in sequences_data.items():
            try:
                seq = ProjectSerializer._deserialize_sequence(seq_id, seq_dict)
                state.add_sequence(seq)
            except Exception as e:
                raise ValueError(f"Failed to deserialize sequence '{seq_id}': {e}")

        # Restore export spec
        export_data = data.get("export_spec", {})
        try:
            state.export_spec = ProjectSerializer._deserialize_export_spec(export_data)
        except Exception as e:
            raise ValueError(f"Failed to deserialize export spec: {e}")

        return state

    @staticmethod
    def save_to_file(state: ProjectState, file_path: Path) -> None:
        """Save project to JSON file."""
        data = ProjectSerializer.serialize(state)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_from_file(file_path: Path) -> ProjectState:
        """Load project from JSON file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Project file not found: {file_path}")
        
        with open(file_path, "r") as f:
            data = json.load(f)
        
        return ProjectSerializer.deserialize(data)

    # ========== Sequence Serialization ==========

    @staticmethod
    def _serialize_sequences(sequences: Dict[str, SequenceSpec]) -> Dict[str, Any]:
        """Serialize all sequences, keyed by ID."""
        result = {}
        for seq_id, seq in sequences.items():
            result[seq_id] = ProjectSerializer._serialize_sequence(seq)
        return result

    @staticmethod
    def _serialize_sequence(seq: SequenceSpec) -> Dict[str, Any]:
        """Serialize a single sequence."""
        return {
            "display_name": seq.display_name,
            "pattern": seq.pattern.pattern,
            "source_dir": str(seq.source_dir),
            "frames": seq.frames,
            # Note: static_probe and per_frame_probes are not serialized
            # They are probed again when loading
        }

    @staticmethod
    def _deserialize_sequence(seq_id: str, data: Dict[str, Any]) -> SequenceSpec:
        """Deserialize a single sequence from data."""
        return SequenceSpec(
            id=seq_id,
            display_name=data.get("display_name", seq_id),
            pattern=SequencePathPattern(data.get("pattern", "")),
            source_dir=Path(data.get("source_dir", "")),
            frames=data.get("frames", []),
            static_probe=None,  # Will need to be re-probed
            per_frame_probes={},
        )

    # ========== Export Spec Serialization ==========

    @staticmethod
    def _serialize_export_spec(spec: ExportSpec) -> Dict[str, Any]:
        """Serialize the export specification."""
        return {
            "output_dir": spec.output_dir,
            "filename_pattern": spec.filename_pattern,
            "output_channels": ProjectSerializer._serialize_output_channels(
                spec.output_channels
            ),
            "output_attributes": ProjectSerializer._serialize_attribute_set(
                spec.output_attributes
            ),
            "frame_policy": spec.frame_policy.name,
            "compression": spec.compression,
            "frame_range": spec.frame_range,
        }

    @staticmethod
    def _deserialize_export_spec(data: Dict[str, Any]) -> ExportSpec:
        """Deserialize export specification from data."""
        frame_policy_name = data.get("frame_policy", "STOP_AT_SHORTEST")
        try:
            frame_policy = FrameRangePolicy[frame_policy_name]
        except KeyError:
            frame_policy = FrameRangePolicy.STOP_AT_SHORTEST

        return ExportSpec(
            output_dir=data.get("output_dir", ""),
            filename_pattern=data.get("filename_pattern", "output.%04d.exr"),
            output_channels=ProjectSerializer._deserialize_output_channels(
                data.get("output_channels", [])
            ),
            output_attributes=ProjectSerializer._deserialize_attribute_set(
                data.get("output_attributes", {})
            ),
            frame_policy=frame_policy,
            compression=data.get("compression", "zip"),
            frame_range=data.get("frame_range"),
        )

    # ========== Output Channel Serialization ==========

    @staticmethod
    def _serialize_output_channels(channels: List[OutputChannel]) -> List[Dict[str, Any]]:
        """Serialize output channels."""
        result = []
        for ch in channels:
            result.append({
                "output_name": ch.output_name,
                "source": {
                    "sequence_id": ch.source.sequence_id,
                    "channel_name": ch.source.channel_name,
                    "subimage_index": ch.source.subimage_index,
                },
                "override_format": None,  # TODO: extend if needed
            })
        return result

    @staticmethod
    def _deserialize_output_channels(data: List[Dict[str, Any]]) -> List[OutputChannel]:
        """Deserialize output channels from data."""
        result = []
        for ch_dict in data:
            source_dict = ch_dict.get("source", {})
            source = ChannelSourceRef(
                sequence_id=source_dict.get("sequence_id", ""),
                channel_name=source_dict.get("channel_name", ""),
                subimage_index=source_dict.get("subimage_index", 0),
            )
            result.append(OutputChannel(
                output_name=ch_dict.get("output_name", ""),
                source=source,
                override_format=None,
            ))
        return result

    # ========== Attribute Serialization ==========

    @staticmethod
    def _serialize_attribute_set(attr_set: AttributeSet) -> List[Dict[str, Any]]:
        """Serialize an AttributeSet."""
        result = []
        for attr in attr_set.attributes:
            result.append(ProjectSerializer._serialize_attribute(attr))
        return result

    @staticmethod
    def _serialize_attribute(attr: AttributeSpec) -> Dict[str, Any]:
        """Serialize a single attribute."""
        # Convert value to JSON-serializable form
        value = attr.value
        if isinstance(value, (list, dict, str, int, float, bool, type(None))):
            serialized_value = value
        else:
            # Fallback: convert to string representation
            serialized_value = str(value)

        return {
            "name": attr.name,
            "oiio_type": attr.oiio_type,
            "value": serialized_value,
            "source": attr.source.name,
            "editable": attr.editable,
            "description": attr.description,
        }

    @staticmethod
    def _deserialize_attribute_set(data: List[Dict[str, Any]]) -> AttributeSet:
        """Deserialize an AttributeSet from data."""
        attrs = []
        for attr_dict in data:
            try:
                source_name = attr_dict.get("source", "CUSTOM")
                source = AttributeSource[source_name]
            except KeyError:
                source = AttributeSource.CUSTOM

            attrs.append(AttributeSpec(
                name=attr_dict.get("name", ""),
                oiio_type=attr_dict.get("oiio_type", "string"),
                value=attr_dict.get("value"),
                source=source,
                editable=attr_dict.get("editable", True),
                description=attr_dict.get("description", ""),
            ))
        return AttributeSet(attributes=attrs)
