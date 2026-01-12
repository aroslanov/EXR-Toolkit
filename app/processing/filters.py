"""
Filter definitions for the processing pipeline.

Each filter represents a specific image processing operation that can be
applied to image data via OpenImageIO's ImageBufAlgo functions.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, List, Dict


class ParameterType(Enum):
    """Type of filter parameter."""
    FLOAT = auto()
    INT = auto()
    CHOICE = auto()
    STRING = auto()
    BOOL = auto()


@dataclass
class FilterParameter:
    """A single parameter for a filter."""
    name: str
    param_type: ParameterType
    value: Any
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    options: Optional[List[str]] = None
    description: str = ""

    def validate(self) -> tuple[bool, str]:
        """Validate parameter value. Returns (is_valid, error_message)."""
        
        if self.param_type == ParameterType.FLOAT:
            if not isinstance(self.value, (int, float)):
                return False, f"{self.name} must be a number"
            if self.min_val is not None and self.value < self.min_val:
                return False, f"{self.name} must be >= {self.min_val}"
            if self.max_val is not None and self.value > self.max_val:
                return False, f"{self.name} must be <= {self.max_val}"
        
        elif self.param_type == ParameterType.INT:
            if not isinstance(self.value, int):
                return False, f"{self.name} must be an integer"
            if self.min_val is not None and self.value < self.min_val:
                return False, f"{self.name} must be >= {int(self.min_val)}"
            if self.max_val is not None and self.value > self.max_val:
                return False, f"{self.name} must be <= {int(self.max_val)}"
        
        elif self.param_type == ParameterType.CHOICE:
            if self.options and self.value not in self.options:
                return False, f"{self.name} must be one of: {', '.join(self.options)}"
        
        elif self.param_type == ParameterType.STRING:
            if not isinstance(self.value, str):
                return False, f"{self.name} must be a string"
        
        elif self.param_type == ParameterType.BOOL:
            if not isinstance(self.value, bool):
                return False, f"{self.name} must be a boolean"
        
        return True, ""


@dataclass
class ProcessingFilter:
    """Base class for all processing filters."""
    filter_id: str
    name: str
    category: str
    enabled: bool = True
    order: int = 0
    parameters: Dict[str, FilterParameter] = field(default_factory=dict)
    
    def validate_parameters(self) -> tuple[bool, List[str]]:
        """Validate all parameters. Returns (is_valid, list_of_errors)."""
        errors = []
        for param in self.parameters.values():
            is_valid, error_msg = param.validate()
            if not is_valid:
                errors.append(error_msg)
        return len(errors) == 0, errors
    
    def get_parameter(self, name: str) -> Optional[FilterParameter]:
        """Get a parameter by name."""
        return self.parameters.get(name)
    
    def set_parameter(self, name: str, value: Any) -> bool:
        """Set a parameter value. Returns success."""
        if name not in self.parameters:
            return False
        self.parameters[name].value = value
        is_valid, _ = self.parameters[name].validate()
        return is_valid
    
    def clone(self) -> "ProcessingFilter":
        """Create a deep copy of this filter with same parameters."""
        from copy import deepcopy
        return deepcopy(self)


# ============================================================================
# FILTER IMPLEMENTATIONS
# ============================================================================

class MedianFilter(ProcessingFilter):
    """Median filter for noise reduction."""
    
    def __init__(self):
        super().__init__(
            filter_id="median_filter",
            name="Median Filter",
            category="Filtering & Repair",
            parameters={
                "kernel_width": FilterParameter(
                    name="Kernel Width",
                    param_type=ParameterType.INT,
                    value=3,
                    min_val=1,
                    max_val=21,
                    options=["1", "3", "5", "7", "9"],
                    description="Width of median kernel (must be odd)"
                ),
                "kernel_height": FilterParameter(
                    name="Kernel Height",
                    param_type=ParameterType.INT,
                    value=3,
                    min_val=1,
                    max_val=21,
                    description="Height of median kernel (must be odd)"
                ),
            }
        )


class UnsharpMaskFilter(ProcessingFilter):
    """Unsharp mask for controlled sharpening."""
    
    def __init__(self):
        super().__init__(
            filter_id="unsharp_mask",
            name="Unsharp Mask",
            category="Filtering & Repair",
            parameters={
                "amount": FilterParameter(
                    name="Amount",
                    param_type=ParameterType.FLOAT,
                    value=0.5,
                    min_val=0.0,
                    max_val=5.0,
                    description="Sharpening intensity (0.0-5.0)"
                ),
                "radius": FilterParameter(
                    name="Radius",
                    param_type=ParameterType.FLOAT,
                    value=1.0,
                    min_val=0.1,
                    max_val=10.0,
                    description="Halo effect size in pixels"
                ),
                "threshold": FilterParameter(
                    name="Threshold",
                    param_type=ParameterType.FLOAT,
                    value=0.0,
                    min_val=0.0,
                    max_val=1.0,
                    description="Minimum difference to sharpen"
                ),
            }
        )


class ColorSpaceConversionFilter(ProcessingFilter):
    """Convert between color spaces."""
    
    def __init__(self):
        super().__init__(
            filter_id="color_space_conversion",
            name="Color Space Conversion",
            category="Color Transforms",
            parameters={
                "from_space": FilterParameter(
                    name="From Color Space",
                    param_type=ParameterType.CHOICE,
                    value="sRGB",
                    options=["sRGB", "scene_linear", "ACEScg", "DCI-P3", "Rec709", "Raw"],
                    description="Source color space"
                ),
                "to_space": FilterParameter(
                    name="To Color Space",
                    param_type=ParameterType.CHOICE,
                    value="scene_linear",
                    options=["sRGB", "scene_linear", "ACEScg", "DCI-P3", "Rec709", "Raw"],
                    description="Destination color space"
                ),
                "unpremult": FilterParameter(
                    name="Unpremultiply Alpha",
                    param_type=ParameterType.BOOL,
                    value=True,
                    description="Separate alpha channel during conversion"
                ),
            }
        )


class BrightnessContrastFilter(ProcessingFilter):
    """Adjust brightness and contrast."""
    
    def __init__(self):
        super().__init__(
            filter_id="brightness_contrast",
            name="Brightness/Contrast",
            category="Tone & Dynamics",
            parameters={
                "brightness": FilterParameter(
                    name="Brightness",
                    param_type=ParameterType.FLOAT,
                    value=1.0,
                    min_val=0.0,
                    max_val=3.0,
                    description="Brightness multiplier (1.0 = no change)"
                ),
                "contrast": FilterParameter(
                    name="Contrast",
                    param_type=ParameterType.FLOAT,
                    value=1.0,
                    min_val=0.0,
                    max_val=3.0,
                    description="Contrast multiplier (1.0 = no change)"
                ),
            }
        )


class GammaCorrectionFilter(ProcessingFilter):
    """Apply gamma correction."""
    
    def __init__(self):
        super().__init__(
            filter_id="gamma_correction",
            name="Gamma Correction",
            category="Tone & Dynamics",
            parameters={
                "gamma": FilterParameter(
                    name="Gamma",
                    param_type=ParameterType.FLOAT,
                    value=1.0,
                    min_val=0.2,
                    max_val=3.0,
                    description="Gamma exponent (1.0 = no change, <1 brightens, >1 darkens)"
                ),
            }
        )


class FillHolesFilter(ProcessingFilter):
    """Fill holes in image using push-pull algorithm."""
    
    def __init__(self):
        super().__init__(
            filter_id="fill_holes",
            name="Fill Holes",
            category="Filtering & Repair",
            parameters={}  # No parameters for this filter
        )


class FixNonFiniteFilter(ProcessingFilter):
    """Replace NaN and Infinity values."""
    
    def __init__(self):
        super().__init__(
            filter_id="fix_non_finite",
            name="Fix Non-Finite",
            category="Filtering & Repair",
            parameters={
                "fill_value": FilterParameter(
                    name="Fill Value",
                    param_type=ParameterType.FLOAT,
                    value=0.0,
                    min_val=-1000.0,
                    max_val=1000.0,
                    description="Value to replace NaN/Infinity with"
                ),
            }
        )


class WarpTransformFilter(ProcessingFilter):
    """Apply geometric warp transform using 3x3 matrix."""
    
    def __init__(self):
        super().__init__(
            filter_id="warp_transform",
            name="Warp Transform",
            category="Effects & Distortion",
            parameters={
                "matrix_mode": FilterParameter(
                    name="Matrix Mode",
                    param_type=ParameterType.CHOICE,
                    value="identity",
                    options=["identity", "custom"],
                    description="Use preset or custom 3x3 matrix"
                ),
            }
        )


class RotateFilter(ProcessingFilter):
    """Rotate image by specified angle."""
    
    def __init__(self):
        super().__init__(
            filter_id="rotate",
            name="Rotate",
            category="Effects & Distortion",
            parameters={
                "angle": FilterParameter(
                    name="Angle",
                    param_type=ParameterType.CHOICE,
                    value="0",
                    options=["0", "90", "180", "270", "arbitrary"],
                    description="Rotation angle in degrees"
                ),
                "arbitrary_angle": FilterParameter(
                    name="Arbitrary Angle",
                    param_type=ParameterType.FLOAT,
                    value=0.0,
                    min_val=-360.0,
                    max_val=360.0,
                    description="Angle in degrees (used if angle is 'arbitrary')"
                ),
            }
        )


class NoiseInjectionFilter(ProcessingFilter):
    """Inject noise into image."""
    
    def __init__(self):
        super().__init__(
            filter_id="noise_injection",
            name="Noise Injection",
            category="Effects & Distortion",
            parameters={
                "noise_type": FilterParameter(
                    name="Noise Type",
                    param_type=ParameterType.CHOICE,
                    value="gaussian",
                    options=["uniform", "gaussian", "salt_pepper"],
                    description="Type of noise to inject"
                ),
                "amount": FilterParameter(
                    name="Amount",
                    param_type=ParameterType.FLOAT,
                    value=0.1,
                    min_val=0.0,
                    max_val=1.0,
                    description="Amount of noise (0.0-1.0)"
                ),
            }
        )


class DilateFilter(ProcessingFilter):
    """Dilate image (morphological operation)."""
    
    def __init__(self):
        super().__init__(
            filter_id="dilate",
            name="Dilate",
            category="Morphological Operations",
            parameters={
                "kernel_width": FilterParameter(
                    name="Kernel Width",
                    param_type=ParameterType.INT,
                    value=3,
                    min_val=1,
                    max_val=21,
                    description="Width of dilation kernel (must be odd)"
                ),
                "kernel_height": FilterParameter(
                    name="Kernel Height",
                    param_type=ParameterType.INT,
                    value=3,
                    min_val=1,
                    max_val=21,
                    description="Height of dilation kernel (must be odd)"
                ),
            }
        )


class ErodeFilter(ProcessingFilter):
    """Erode image (morphological operation)."""
    
    def __init__(self):
        super().__init__(
            filter_id="erode",
            name="Erode",
            category="Morphological Operations",
            parameters={
                "kernel_width": FilterParameter(
                    name="Kernel Width",
                    param_type=ParameterType.INT,
                    value=3,
                    min_val=1,
                    max_val=21,
                    description="Width of erosion kernel (must be odd)"
                ),
                "kernel_height": FilterParameter(
                    name="Kernel Height",
                    param_type=ParameterType.INT,
                    value=3,
                    min_val=1,
                    max_val=21,
                    description="Height of erosion kernel (must be odd)"
                ),
            }
        )


class ChannelExtractFilter(ProcessingFilter):
    """Extract and reorder specific channels."""
    
    def __init__(self):
        super().__init__(
            filter_id="channel_extract",
            name="Channel Extract",
            category="Channel Operations",
            parameters={
                "channels": FilterParameter(
                    name="Channels",
                    param_type=ParameterType.STRING,
                    value="R,G,B",
                    description="Comma-separated channel names to extract"
                ),
            }
        )


class ChannelInvertFilter(ProcessingFilter):
    """Invert pixel values (1 - value) per channel."""
    
    def __init__(self):
        super().__init__(
            filter_id="channel_invert",
            name="Channel Invert",
            category="Channel Operations",
            parameters={
                "channels": FilterParameter(
                    name="Channels",
                    param_type=ParameterType.STRING,
                    value="R,G,B",
                    description="Comma-separated channels to invert (empty = all)"
                ),
            }
        )


# Registry of all available filters
FILTER_REGISTRY = {
    "median_filter": MedianFilter,
    "unsharp_mask": UnsharpMaskFilter,
    "color_space_conversion": ColorSpaceConversionFilter,
    "brightness_contrast": BrightnessContrastFilter,
    "gamma_correction": GammaCorrectionFilter,
    "fill_holes": FillHolesFilter,
    "fix_non_finite": FixNonFiniteFilter,
    "warp_transform": WarpTransformFilter,
    "rotate": RotateFilter,
    "noise_injection": NoiseInjectionFilter,
    "dilate": DilateFilter,
    "erode": ErodeFilter,
    "channel_extract": ChannelExtractFilter,
    "channel_invert": ChannelInvertFilter,
}


def create_filter(filter_id: str) -> Optional[ProcessingFilter]:
    """Create a filter instance by ID. Returns None if filter not found."""
    if filter_id not in FILTER_REGISTRY:
        return None
    return FILTER_REGISTRY[filter_id]()


def get_filters_by_category(category: str) -> List[ProcessingFilter]:
    """Get all filters in a specific category."""
    filters = []
    for filter_class in FILTER_REGISTRY.values():
        f = filter_class()
        if f.category == category:
            filters.append(f)
    return filters


def get_all_categories() -> List[str]:
    """Get all filter categories in order."""
    categories = []
    seen = set()
    for filter_class in FILTER_REGISTRY.values():
        f = filter_class()
        if f.category not in seen:
            categories.append(f.category)
            seen.add(f.category)
    
    # Return in preferred order
    preferred_order = [
        "Color Transforms",
        "Tone & Dynamics",
        "Filtering & Repair",
        "Effects & Distortion",
        "Morphological Operations",
        "Channel Operations",
    ]
    
    # Return in preferred order, then any others
    result = []
    for cat in preferred_order:
        if cat in categories:
            result.append(cat)
    for cat in categories:
        if cat not in result:
            result.append(cat)
    
    return result
