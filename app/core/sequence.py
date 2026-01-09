"""
Sequence pattern parsing and frame discovery.
"""

import re
from pathlib import Path
from typing import List, Optional

from .types import SequencePathPattern, SequenceSpec, FileProbe


class SequenceDiscovery:
    """Discovers image frames matching a pattern."""

    @staticmethod
    def discover_frames(pattern_str: str, directory: str) -> List[int]:
        """
        Scan directory for files matching pattern; return sorted frame numbers.

        Pattern format:
        - %04d (printf-style)
        - #### (hash-style)
        """
        pattern = SequencePathPattern(pattern_str)
        
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return []

        # Build regex
        regex_str = _pattern_to_regex(pattern_str)
        regex = re.compile(regex_str)

        frames = set()
        for file_path in dir_path.iterdir():
            if file_path.is_file():
                match = regex.match(file_path.name)
                if match:
                    try:
                        frame_num = int(match.group(1))
                        frames.add(frame_num)
                    except (IndexError, ValueError):
                        continue

        return sorted(frames)


def _pattern_to_regex(pattern: str) -> str:
    """Convert %04d or #### patterns to regex."""
    # Escape the pattern for use in regex
    escaped = re.escape(pattern)
    
    # Replace escaped printf-style: \%0\d+d -> (\d+)
    # Use lambda to avoid backslash interpretation in replacement string
    escaped = re.sub(r"\\%0\d+d", lambda m: r"(\d+)", escaped)
    
    # Replace escaped hash-style: \#+  -> (\d+)
    escaped = re.sub(r"\\#+", lambda m: r"(\d+)", escaped)
    
    return f"^{escaped}$"
