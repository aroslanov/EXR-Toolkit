"""
Core data types for EXR Toolkit.

All types use @dataclass and Enum for structured, immutable representations.
No loose dicts at the internal API boundary.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, TYPE_CHECKING
from pathlib import Path

# Avoid circular imports
if TYPE_CHECKING:
    from ..processing import ProcessingPipeline


class AttributeSource(Enum):
    """Where an attribute originates."""
    INPUT_SEQ = auto()
    OUTPUT_OVERRIDE = auto()
    MERGED = auto()
    CUSTOM = auto()


class FrameRangePolicy(Enum):
    """How to handle sequences of different lengths."""
    STOP_AT_SHORTEST = auto()
    HOLD_LAST = auto()
    PROCESS_AVAILABLE = auto()


class ValidationSeverity(Enum):
    """Validation issue severity."""
    ERROR = auto()
    WARNING = auto()


@dataclass
class ChannelFormat:
    """Wraps OIIO channel type information."""
    oiio_type: str  # e.g., "float", "half", "uint32", etc.
    description: str = ""  # human-readable description


@dataclass
class ChannelSourceRef:
    """Reference to a channel in a source sequence."""
    sequence_id: str
    channel_name: str
    subimage_index: int = 0


@dataclass
class ChannelSpec:
    """Immutable channel specification."""
    name: str
    format: ChannelFormat
    source: Optional[ChannelSourceRef] = None
    subimage_index: int = 0


@dataclass
class AttributeSpec:
    """Immutable attribute specification."""
    name: str
    oiio_type: str  # string representation of OIIO TypeDesc
    value: Any  # type-consistent with oiio_type
    source: AttributeSource = AttributeSource.CUSTOM
    editable: bool = True
    description: str = ""


@dataclass
class AttributeSet:
    """Collection of attributes with lookup helpers."""
    attributes: list[AttributeSpec] = field(default_factory=list)

    def get_by_name(self, name: str) -> Optional[AttributeSpec]:
        """Find attribute by name."""
        for attr in self.attributes:
            if attr.name == name:
                return attr
        return None

    def add_or_update(self, attr: AttributeSpec) -> None:
        """Add new attribute or update existing one by name."""
        existing = self.get_by_name(attr.name)
        if existing:
            idx = self.attributes.index(existing)
            self.attributes[idx] = attr
        else:
            self.attributes.append(attr)

    def names(self) -> list[str]:
        """List all attribute names."""
        return [attr.name for attr in self.attributes]

    def __len__(self) -> int:
        return len(self.attributes)


@dataclass
class ImageSpecSnapshot:
    """Immutable snapshot of OIIO ImageSpec fields we care about."""
    width: int
    height: int
    nchannels: int
    channelnames: list[str]
    channelformats: list[str]  # per-channel OIIO type strings
    tile_width: int = 0
    tile_height: int = 0
    format: str = "unknown"  # pixel format


@dataclass
class SubImageProbe:
    """Probed data from one subimage/part of a file."""
    spec: ImageSpecSnapshot
    channels: list[ChannelSpec]
    attributes: AttributeSet


@dataclass
class FileProbe:
    """Probed data from a single file."""
    path: str
    subimages: list[SubImageProbe] = field(default_factory=list)

    @property
    def main_subimage(self) -> Optional[SubImageProbe]:
        """Shorthand for primary subimage (index 0)."""
        return self.subimages[0] if self.subimages else None


@dataclass
class SequencePathPattern:
    """Parses and formats sequence path patterns."""
    pattern: str

    def to_regex(self) -> str:
        """Convert pattern to regex for frame discovery."""
        import re
        # Support %04d (printf) and #### (hash) styles
        regex = re.escape(self.pattern)
        regex = regex.replace(r"\%0\d+d", r"(\d+)")
        regex = regex.replace(r"\#\#+", r"(\d+)")
        return f"^{regex}$"

    def format(self, frame: int) -> str:
        """Format a frame number into the pattern."""
        import re
        result = self.pattern
        # %04d style
        result = re.sub(r"%0(\d+)d", lambda m: str(frame).zfill(int(m.group(1))), result)
        # #### style (count # chars)
        def format_hashes(m):
            width = len(m.group(0))
            return str(frame).zfill(width)
        result = re.sub(r"#+", format_hashes, result)
        return result


@dataclass
class SequenceSpec:
    """Specification for a single image sequence."""
    id: str
    display_name: str
    pattern: SequencePathPattern
    source_dir: Path  # Directory containing the source sequence files
    frames: list[int] = field(default_factory=list)
    static_probe: Optional[FileProbe] = None
    per_frame_probes: dict[int, FileProbe] = field(default_factory=dict)

    def probe(self, frame: Optional[int] = None) -> Optional[FileProbe]:
        """Get probed data for a specific frame (or static probe if None)."""
        if frame is None:
            return self.static_probe
        return self.per_frame_probes.get(frame)


@dataclass
class OutputChannel:
    """Definition of a channel in the output."""
    output_name: str
    source: ChannelSourceRef
    override_format: Optional[ChannelFormat] = None


@dataclass
class ExportSpec:
    """Complete export specification."""
    output_dir: str
    filename_pattern: str  # e.g., "beauty.%04d.exr"
    output_channels: list[OutputChannel] = field(default_factory=list)
    output_attributes: AttributeSet = field(default_factory=AttributeSet)
    frame_policy: FrameRangePolicy = FrameRangePolicy.STOP_AT_SHORTEST
    compression: str = "zip"  # OIIO EXR compression name
    compression_policy: str = "skip"  # "skip" or "always" - recompression optimization
    frame_range: Optional[tuple[int, int]] = None  # (start, end) inclusive


@dataclass
class ValidationIssue:
    """A validation problem."""
    severity: ValidationSeverity
    code: str
    message: str
    context: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.severity.name}] {self.code}: {self.message}"

@dataclass
class ProcessingConfig:
    """Configuration for image processing pipeline."""
    enabled: bool = False
    preview_frame: Optional[int] = None
    # Note: actual pipeline stored separately via ProcessingPipeline instance
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "enabled": self.enabled,
            "preview_frame": self.preview_frame,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProcessingConfig":
        """Deserialize from dictionary."""
        return cls(
            enabled=data.get("enabled", False),
            preview_frame=data.get("preview_frame"),
        )