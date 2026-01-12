"""
Processing system for EXR Toolkit.

Provides non-destructive image processing filters that operate on frames
during export. Filters are stored as configurations and applied sequentially
via OpenImageIO's ImageBufAlgo.
"""

from .pipeline import ProcessingPipeline
from .filters import (
    ProcessingFilter,
    FilterParameter,
    ParameterType,
    MedianFilter,
    UnsharpMaskFilter,
    ColorSpaceConversionFilter,
    BrightnessContrastFilter,
    GammaCorrectionFilter,
    FillHolesFilter,
    FixNonFiniteFilter,
    WarpTransformFilter,
    RotateFilter,
    NoiseInjectionFilter,
    DilateFilter,
    ErodeFilter,
    ChannelExtractFilter,
    ChannelInvertFilter,
)
from .executor import ProcessingExecutor
from .filters import (
    create_filter,
    get_filters_by_category,
    get_all_categories,
    FILTER_REGISTRY,
)

__all__ = [
    "ProcessingPipeline",
    "ProcessingFilter",
    "FilterParameter",
    "ParameterType",
    "ProcessingExecutor",
    # Helpers
    "create_filter",
    "get_filters_by_category",
    "get_all_categories",
    "FILTER_REGISTRY",
    # Filters
    "MedianFilter",
    "UnsharpMaskFilter",
    "ColorSpaceConversionFilter",
    "BrightnessContrastFilter",
    "GammaCorrectionFilter",
    "FillHolesFilter",
    "FixNonFiniteFilter",
    "WarpTransformFilter",
    "RotateFilter",
    "NoiseInjectionFilter",
    "DilateFilter",
    "ErodeFilter",
    "ChannelExtractFilter",
    "ChannelInvertFilter",
]
