"""
OpenImageIO adapter for robust, version-safe interaction.

Handles API differences across OIIO versions and normalizes
spec/attribute enumeration.
"""

from typing import List, Optional, Any, Tuple
import OpenImageIO as oiio

from ..core import (
    ChannelFormat,
    ChannelSpec,
    AttributeSpec,
    AttributeSet,
    AttributeSource,
    ImageSpecSnapshot,
    SubImageProbe,
    FileProbe,
)


class OiioAdapter:
    """Thin wrapper for robust OIIO bindings."""

    @staticmethod
    def probe_file(filepath: str) -> Optional[FileProbe]:
        """
        Probe a file: read all subimages and extract channels + attributes.
        Returns FileProbe or None if file cannot be read.
        """
        try:
            inp = oiio.ImageInput.open(filepath)
            if not inp:
                return None

            subimages = []
            subimage_idx = 0

            while True:
                spec = inp.spec()
                if not spec:
                    break

                subimage = OiioAdapter._probe_subimage(spec, subimage_idx)
                subimages.append(subimage)

                # Try to move to next subimage
                if not inp.seek_subimage(subimage_idx + 1, 0):
                    break
                subimage_idx += 1

            inp.close()
            return FileProbe(path=filepath, subimages=subimages)

        except Exception as e:
            print(f"[OIIO] Error probing {filepath}: {e}")
            return None

    @staticmethod
    def _probe_subimage(spec: oiio.ImageSpec, subimage_idx: int) -> SubImageProbe:
        """Extract channel and attribute data from a single subimage."""
        
        # Extract channel information
        channels = OiioAdapter._extract_channels(spec, subimage_idx)
        
        # Extract attributes
        attributes = OiioAdapter._extract_attributes(spec)
        
        # Create spec snapshot
        spec_snapshot = OiioAdapter._snapshot_spec(spec)
        
        return SubImageProbe(
            spec=spec_snapshot,
            channels=channels,
            attributes=attributes,
        )

    @staticmethod
    def _extract_channels(spec: oiio.ImageSpec, subimage_idx: int) -> List[ChannelSpec]:
        """Extract channel list from spec."""
        channels = []
        
        # Get channel names
        channel_names = spec.channelnames if hasattr(spec, 'channelnames') else []
        if not channel_names:
            # Fallback: generic channel names
            nchannels = spec.nchannels
            channel_names = [f"channel{i}" for i in range(nchannels)]
        
        # Get channel formats (per-channel OIIO types)
        channel_formats = spec.channelformats if hasattr(spec, 'channelformats') else []
        if not channel_formats and hasattr(spec, 'format'):
            # Fallback: all channels same format
            channel_formats = [str(spec.format)] * len(channel_names)
        
        for i, ch_name in enumerate(channel_names):
            fmt_str = channel_formats[i] if i < len(channel_formats) else "unknown"
            fmt = ChannelFormat(oiio_type=fmt_str)
            
            channels.append(ChannelSpec(
                name=ch_name,
                format=fmt,
                subimage_index=subimage_idx,
            ))
        
        return channels

    @staticmethod
    def _extract_attributes(spec: oiio.ImageSpec) -> AttributeSet:
        """Extract all attributes from spec."""
        attributes = AttributeSet()
        
        # Try different ways to enumerate attributes depending on OIIO version
        
        # Method 1: extra_attribs (newer OIIO)
        if hasattr(spec, 'extra_attribs'):
            for attr in spec.extra_attribs:
                try:
                    attr_spec = AttributeSpec(
                        name=attr.name,
                        oiio_type=str(attr.type),
                        value=attr.value,
                        source=AttributeSource.INPUT_SEQ,
                        editable=True,
                    )
                    attributes.add_or_update(attr_spec)
                except Exception:
                    pass
        
        # Method 2: Use attrib() getter (fallback for specific known attributes)
        # This is a manual list of common EXR attributes to check
        common_attrs = [
            "compression",
            "lineOrder",
            "pixelAspectRatio",
            "expTime",
            "renderingTransform",
            "displayWindow",
            "dataWindow",
            "openexr:lineOrder",
            "openexr:compressionType",
        ]
        
        for attr_name in common_attrs:
            try:
                val = spec.getattribute(attr_name)
                if val is not None:
                    attr_spec = AttributeSpec(
                        name=attr_name,
                        oiio_type="mixed",
                        value=val,
                        source=AttributeSource.INPUT_SEQ,
                        editable=True,
                    )
                    # Only add if not already in set
                    if attributes.get_by_name(attr_name) is None:
                        attributes.add_or_update(attr_spec)
            except Exception:
                pass
        
        return attributes

    @staticmethod
    def _snapshot_spec(spec: oiio.ImageSpec) -> ImageSpecSnapshot:
        """Create an immutable snapshot of critical spec fields."""
        
        width = spec.width
        height = spec.height
        nchannels = spec.nchannels
        
        channel_names = list(spec.channelnames) if hasattr(spec, 'channelnames') else []
        if not channel_names:
            channel_names = [f"channel{i}" for i in range(nchannels)]
        
        channel_formats = list(spec.channelformats) if hasattr(spec, 'channelformats') else []
        if not channel_formats:
            fmt_str = str(spec.format) if hasattr(spec, 'format') else "unknown"
            channel_formats = [fmt_str] * len(channel_names)
        
        tile_width = spec.tile_width if hasattr(spec, 'tile_width') else 0
        tile_height = spec.tile_height if hasattr(spec, 'tile_height') else 0
        
        return ImageSpecSnapshot(
            width=width,
            height=height,
            nchannels=nchannels,
            channelnames=channel_names,
            channelformats=channel_formats,
            tile_width=tile_width,
            tile_height=tile_height,
            format=str(spec.format) if hasattr(spec, 'format') else "unknown",
        )

    @staticmethod
    def get_oiio_version() -> str:
        """Return OIIO version string."""
        try:
            # Try common version attributes
            if hasattr(oiio, '__version__'):
                return str(oiio.__version__)
        except Exception:
            pass
        return "unknown"
