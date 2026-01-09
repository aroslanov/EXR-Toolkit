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
    def discover_sequences(directory: str) -> List[tuple[str, List[int]]]:
        """
        Auto-discover all image sequences in directory.
        
        Returns list of (pattern_str, frame_list) tuples.
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return []
        
        # Collect all files
        files = sorted([f.name for f in dir_path.iterdir() if f.is_file()])
        if not files:
            return []
        
        # Heuristic: look for common image extensions
        image_exts = {'.exr', '.jpg', '.jpeg', '.png', '.tiff', '.tif'}
        image_files = [f for f in files if Path(f).suffix.lower() in image_exts]
        if not image_files:
            return []
        
        # Group by base pattern
        sequences = {}
        for filename in image_files:
            # Match any sequence of digits (variable length)
            match_digits = re.search(r'^(.+?)(\d+)(\..+?)$', filename)
            
            if match_digits:
                base, num_str, ext = match_digits.groups()
                num_len = len(num_str)
                
                # Generate pattern: %0Nd format (e.g., %05d for 5 digits)
                pattern = f"{base}%0{num_len}d{ext}"
                if pattern not in sequences:
                    sequences[pattern] = set()
                try:
                    sequences[pattern].add(int(num_str))
                except ValueError:
                    pass
        
        # Convert sets to sorted lists and return
        result = []
        for pattern, frames in sorted(sequences.items()):
            if frames:
                result.append((pattern, sorted(frames)))
        
        return result

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
    """Convert %0Nd or #### patterns to regex."""
    # Escape the pattern for use in regex
    escaped = re.escape(pattern)
    
    # Replace printf-style %0Nd with capture group (\d+)
    # Use lambda to properly handle backslashes in the replacement
    escaped = re.sub(r"%0\d+d", lambda m: r"(\d+)", escaped)
    
    # Replace hash-style #### with capture group (\d+)
    escaped = re.sub(r"#+", lambda m: r"(\d+)", escaped)
    
    return f"^{escaped}$"
