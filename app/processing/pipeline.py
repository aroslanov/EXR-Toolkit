"""
Processing pipeline management.

Manages a chain of filters that are applied sequentially to image data.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from .filters import ProcessingFilter


@dataclass
class ProcessingPipeline:
    """Container for a sequence of processing filters."""
    
    filters: List[ProcessingFilter] = field(default_factory=list)
    enabled: bool = True
    preview_frame: Optional[int] = None
    
    def add_filter(self, filter: ProcessingFilter) -> None:
        """Add a filter to the pipeline."""
        filter.order = len(self.filters)
        self.filters.append(filter)
    
    def remove_filter(self, index: int) -> bool:
        """Remove a filter by index. Returns success."""
        if 0 <= index < len(self.filters):
            del self.filters[index]
            # Update order
            for i, f in enumerate(self.filters):
                f.order = i
            return True
        return False
    
    def move_filter(self, from_index: int, to_index: int) -> bool:
        """Move a filter from one position to another. Returns success."""
        if not (0 <= from_index < len(self.filters) and 0 <= to_index < len(self.filters)):
            return False
        
        filter = self.filters.pop(from_index)
        self.filters.insert(to_index, filter)
        
        # Update order
        for i, f in enumerate(self.filters):
            f.order = i
        
        return True
    
    def get_filter(self, index: int) -> Optional[ProcessingFilter]:
        """Get a filter by index."""
        if 0 <= index < len(self.filters):
            return self.filters[index]
        return None
    
    def validate(self) -> tuple[bool, List[str]]:
        """Validate all filters in pipeline. Returns (is_valid, errors)."""
        errors = []
        for i, filter in enumerate(self.filters):
            is_valid, filter_errors = filter.validate_parameters()
            if not is_valid:
                for error in filter_errors:
                    errors.append(f"Filter {i} ({filter.name}): {error}")
        return len(errors) == 0, errors
    
    def clear(self) -> None:
        """Remove all filters from pipeline."""
        self.filters.clear()
    
    def is_empty(self) -> bool:
        """Check if pipeline has any filters."""
        return len(self.filters) == 0
    
    def get_enabled_filters(self) -> List[ProcessingFilter]:
        """Get list of enabled filters in order."""
        if not self.enabled:
            return []
        return [f for f in self.filters if f.enabled]
    
    def __len__(self) -> int:
        """Return number of filters in pipeline."""
        return len(self.filters)
    
    def __iter__(self):
        """Iterate over filters in pipeline."""
        return iter(self.filters)
