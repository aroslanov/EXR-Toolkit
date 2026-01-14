"""Image resize utilities for sequence normalization."""

from typing import List, Tuple

from ..core import SequenceSpec, ResizePolicy, ResizeAlgorithm


def calculate_target_size(
    sequences: List[SequenceSpec],
    policy: ResizePolicy,
    custom_width: int = 0,
    custom_height: int = 0,
) -> Tuple[int, int]:
    """
    Calculate target resize dimensions based on policy.
    
    Args:
        sequences: List of loaded sequences
        policy: ResizePolicy enum value
        custom_width: Width if policy is CUSTOM
        custom_height: Height if policy is CUSTOM
    
    Returns:
        (width, height) tuple
    """
    if not sequences or policy == ResizePolicy.NONE:
        # Return first sequence's size or (0, 0)
        if sequences and sequences[0].static_probe and sequences[0].static_probe.main_subimage:
            spec = sequences[0].static_probe.main_subimage.spec
            return spec.width, spec.height
        return 0, 0
    
    # Collect all dimensions
    dimensions = []
    for seq in sequences:
        if seq.static_probe and seq.static_probe.main_subimage:
            spec = seq.static_probe.main_subimage.spec
            dimensions.append((spec.width, spec.height))
    
    if not dimensions:
        return 0, 0
    
    if policy == ResizePolicy.LARGEST:
        widths = [d[0] for d in dimensions]
        heights = [d[1] for d in dimensions]
        return max(widths), max(heights)
    
    elif policy == ResizePolicy.SMALLEST:
        widths = [d[0] for d in dimensions]
        heights = [d[1] for d in dimensions]
        return min(widths), min(heights)
    
    elif policy == ResizePolicy.AVERAGE:
        widths = [d[0] for d in dimensions]
        heights = [d[1] for d in dimensions]
        return int(sum(widths) / len(widths)), int(sum(heights) / len(heights))
    
    elif policy == ResizePolicy.CUSTOM:
        return custom_width, custom_height
    
    return 0, 0


def get_filter_name(algorithm: ResizeAlgorithm) -> str:
    """Map ResizeAlgorithm to OIIO filter name."""
    algo_map = {
        ResizeAlgorithm.LINEAR: "linear",
        ResizeAlgorithm.CUBIC: "cubic",
        ResizeAlgorithm.LANCZOS3: "lanczos3",
        ResizeAlgorithm.NEAREST: "nearest",
    }
    return algo_map.get(algorithm, "lanczos3")
