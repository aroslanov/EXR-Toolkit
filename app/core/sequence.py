"""
Sequence pattern parsing and frame discovery.

Implements parallel batch processing for large directories using ThreadPoolExecutor
while maintaining API compatibility with the sequential version.
"""

import re
import os
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from .types import SequencePathPattern, SequenceSpec, FileProbe


class SequenceDiscovery:
    """Discovers image frames matching a pattern."""

    @staticmethod
    def _calculate_optimal_workers(file_count: int) -> int:
        """
        Calculate optimal number of worker threads based on file count.
        
        Strategy:
        - Small directories (<100 files): 1 worker (sequential, overhead not worth it)
        - Medium directories (100-1000 files): min(4, cpu_count)
        - Large directories (>1000 files): min(8, cpu_count)
        
        Args:
            file_count: Number of files to process
        
        Returns:
            Optimal number of workers (1 = sequential fallback)
        """
        if file_count < 100:
            return 1  # Sequential fallback for small directories
        
        available_cores = os.cpu_count() or 4
        
        if file_count < 1000:
            return min(4, available_cores)
        else:
            return min(8, available_cores)

    @staticmethod
    def _process_sequences_batch(
        filenames: List[str],
        image_exts: set = None
    ) -> dict:
        """
        Process a batch of filenames to extract sequence patterns.
        
        This method is designed to be called from multiple threads.
        Each thread processes a chunk of filenames independently.
        
        Args:
            filenames: List of filenames to process
            image_exts: Set of valid image extensions
        
        Returns:
            Dictionary mapping pattern_str -> set of frame numbers
        """
        if image_exts is None:
            image_exts = {'.exr', '.jpg', '.jpeg', '.png', '.tiff', '.tif'}
        
        sequences = {}
        
        for filename in filenames:
            # Filter by extension
            if Path(filename).suffix.lower() not in image_exts:
                continue
            
            # Extract frame number: search from right to find digits immediately before extension
            # This handles cases like seq_1.0000.exr where 0000 (not 1) is the frame number
            last_dot_idx = filename.rfind('.')
            if last_dot_idx == -1:
                continue
            
            # Look backwards from the dot to find the frame number
            name_before_ext = filename[:last_dot_idx]
            ext = filename[last_dot_idx:]
            
            # Find the rightmost sequence of digits before the extension
            match_digits = re.search(r'(\d+)$', name_before_ext)
            
            if match_digits:
                num_str = match_digits.group(1)
                num_len = len(num_str)
                
                # Get the base (everything before the frame number)
                base = name_before_ext[:match_digits.start()]
                
                # Generate pattern: %0Nd format (e.g., %05d for 5 digits)
                pattern = f"{base}%0{num_len}d{ext}"
                if pattern not in sequences:
                    sequences[pattern] = set()
                try:
                    sequences[pattern].add(int(num_str))
                except ValueError:
                    pass
        
        return sequences

    @staticmethod
    def _process_frames_batch(
        filenames: List[str],
        regex: 're.Pattern'
    ) -> set:
        """
        Process a batch of filenames to extract frame numbers.
        
        This method is designed to be called from multiple threads.
        Each thread processes a chunk of filenames independently.
        
        Args:
            filenames: List of filenames to process
            regex: Compiled regex pattern for matching
        
        Returns:
            Set of frame numbers found
        """
        frames = set()
        
        for filename in filenames:
            match = regex.match(filename)
            if match:
                try:
                    frame_num = int(match.group(1))
                    frames.add(frame_num)
                except (IndexError, ValueError):
                    continue
        
        return frames

    @staticmethod
    def discover_sequences(directory: str) -> List[tuple[str, List[int]]]:
        """
        Auto-discover all image sequences in directory.
        
        Parallelized for directories with 100+ files using ThreadPoolExecutor.
        For small directories, falls back to sequential processing.
        
        Returns list of (pattern_str, frame_list) tuples.
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return []
        
        # Phase 1: Collect all files (sequential, single I/O operation)
        files = sorted([f.name for f in dir_path.iterdir() if f.is_file()])
        if not files:
            return []
        
        # Phase 2: Filter by image extensions (sequential, fast)
        image_exts = {'.exr', '.jpg', '.jpeg', '.png', '.tiff', '.tif'}
        image_files = [f for f in files if Path(f).suffix.lower() in image_exts]
        if not image_files:
            return []
        
        # Phase 3: Determine parallelization strategy
        optimal_workers = SequenceDiscovery._calculate_optimal_workers(len(image_files))
        
        # Phase 4: Process patterns (parallel or sequential)
        if optimal_workers == 1:
            # Sequential fallback for small directories
            all_sequences = SequenceDiscovery._process_sequences_batch(image_files, image_exts)
        else:
            # Parallel processing with chunking
            chunk_size = max(50, len(image_files) // optimal_workers)
            chunks = [
                image_files[i:i+chunk_size]
                for i in range(0, len(image_files), chunk_size)
            ]
            
            all_sequences = {}
            
            # Process chunks in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
                batch_processor = partial(
                    SequenceDiscovery._process_sequences_batch,
                    image_exts=image_exts
                )
                
                # Map function over chunks and collect results
                for batch_result in executor.map(batch_processor, chunks):
                    # Merge batch results into all_sequences
                    for pattern, frames in batch_result.items():
                        if pattern not in all_sequences:
                            all_sequences[pattern] = set()
                        all_sequences[pattern].update(frames)
        
        # Phase 5: Convert to return format and sort
        result = []
        for pattern in sorted(all_sequences.keys()):
            frames = sorted(all_sequences[pattern])
            if frames:
                result.append((pattern, frames))
        
        return result

    @staticmethod
    def discover_frames(pattern_str: str, directory: str) -> List[int]:
        """
        Scan directory for files matching pattern; return sorted frame numbers.
        
        Parallelized for directories with 100+ files using ThreadPoolExecutor.
        For small directories, falls back to sequential processing.

        Pattern format:
        - %04d (printf-style)
        - #### (hash-style)
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return []

        # Phase 1: Collect all files (sequential, single I/O operation)
        files = sorted([f.name for f in dir_path.iterdir() if f.is_file()])
        if not files:
            return []
        
        # Phase 2: Build regex pattern
        regex_str = _pattern_to_regex(pattern_str)
        regex = re.compile(regex_str)
        
        # Phase 3: Determine parallelization strategy
        optimal_workers = SequenceDiscovery._calculate_optimal_workers(len(files))
        
        # Phase 4: Process frames (parallel or sequential)
        if optimal_workers == 1:
            # Sequential fallback for small directories
            all_frames = SequenceDiscovery._process_frames_batch(files, regex)
        else:
            # Parallel processing with chunking
            chunk_size = max(50, len(files) // optimal_workers)
            chunks = [
                files[i:i+chunk_size]
                for i in range(0, len(files), chunk_size)
            ]
            
            all_frames = set()
            
            # Process chunks in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
                batch_processor = partial(
                    SequenceDiscovery._process_frames_batch,
                    regex=regex
                )
                
                # Map function over chunks and collect results
                for batch_frames in executor.map(batch_processor, chunks):
                    all_frames.update(batch_frames)
        
        return sorted(all_frames)


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
