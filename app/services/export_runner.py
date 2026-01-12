"""
Threaded export runner for EXR sequence export.

Runs in a QThread/QRunnable, emits progress/log signals.
Performs validation, channel recombination, and EXR writing.

Supports parallel frame processing via ThreadPoolExecutor.
"""

from pathlib import Path
from typing import List, Optional
import traceback
import threading
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QObject, QThread, Signal, QRunnable, QThreadPool

import OpenImageIO as oiio
import numpy as np

from ..core import (
    ExportSpec,
    SequenceSpec,
    ValidationEngine,
    ValidationSeverity,
)
from ..oiio import OiioAdapter


class ExportSignals(QObject):
    """Signals emitted by ExportRunner."""
    progress = Signal(int, str)  # (percent, message)
    finished = Signal(bool, str)  # (success, final_message)
    log = Signal(str)  # log message


class AtomicProgress:
    """Thread-safe progress counter for parallel workers."""

    def __init__(self, total: int):
        self.lock = threading.Lock()
        self.completed = 0
        self.total = total
        self.last_logged_frame = -1

    def increment(self, frame_num: int) -> int:
        """
        Increment progress counter.
        Returns current percentage (0-100).
        """
        with self.lock:
            self.completed += 1
            self.last_logged_frame = frame_num
            return int((self.completed / self.total) * 100)

    def get_percent(self) -> int:
        """Get current progress percentage."""
        with self.lock:
            return int((self.completed / self.total) * 100)

    def get_completed(self) -> int:
        """Get number of completed frames."""
        with self.lock:
            return self.completed


class ExportRunner(QRunnable):
    """Runnable for export operations."""
    
    # Thread lock for OIIO operations (OIIO may not be thread-safe)
    _oiio_lock = threading.Lock()

    def __init__(
        self,
        export_spec: ExportSpec,
        sequences: dict[str, SequenceSpec],
        compression_policy: str = "skip",
    ):
        super().__init__()
        self.export_spec = export_spec
        self.sequences = sequences
        self.compression_policy = compression_policy  # 'skip' or 'always'
        self.signals = ExportSignals()
        self.stop_requested = False  # Flag to stop export

    def request_stop(self) -> None:
        """Request the export to stop gracefully."""
        self.stop_requested = True

    @staticmethod
    def can_skip_recompression(
        export_spec: ExportSpec,
        sequences: dict[str, SequenceSpec],
        compression_policy: str = "skip",
    ) -> tuple[bool, str]:
        """
        Determine if recompression can be skipped.
        
        Args:
            export_spec: Export specification
            sequences: Available sequences
            compression_policy: 'skip' (default) to skip when possible, 'always' to never skip
        
        Returns (can_skip, reason_explanation).
        Recompression can be skipped when:
        1. Compression policy allows it ('skip' mode)
        2. All output channels come from SAME source sequence
        3. Output includes ALL channels from source (no subset)
        4. Source and target compression match
        5. No attribute modifications from source
        6. No channel format overrides
        """
        # Check 0: Compression policy
        if compression_policy == "always":
            return False, "Compression policy: always recompress"
        
        # Check 1: Single source sequence
        source_seq_ids = set(
            ch.source.sequence_id 
            for ch in export_spec.output_channels
        )
        if len(source_seq_ids) != 1:
            return False, f"Multiple source sequences ({len(source_seq_ids)})"
        
        seq_id = list(source_seq_ids)[0]
        source_seq = sequences.get(seq_id)
        if not source_seq or not source_seq.static_probe:
            return False, f"Source sequence '{seq_id}' not found or not probed"
        
        source_subimage = source_seq.static_probe.main_subimage
        if not source_subimage:
            return False, "Source file has no main subimage"
        
        # Check 2: Output includes ALL source channels
        source_channel_names = set(ch.name for ch in source_subimage.channels)
        output_channel_names = set(
            ch.source.channel_name 
            for ch in export_spec.output_channels
        )
        
        if source_channel_names != output_channel_names:
            return False, "Output is subset/superset of source channels"
        
        # Check 3: Compression matches
        source_compression = OiioAdapter.get_compression_from_probe(
            source_seq.static_probe, 0
        )
        
        # Normalize compression names (handle case variations)
        source_comp_normalized = source_compression.lower() if source_compression else "none"
        target_comp_normalized = export_spec.compression.lower()
        
        if source_comp_normalized != target_comp_normalized:
            return False, f"Compression mismatch: {source_comp_normalized} vs {target_comp_normalized}"
        
        # Check 4: No attribute modifications
        source_attrs = source_subimage.attributes
        output_attrs = export_spec.output_attributes
        
        # Compare attribute count and values
        if len(source_attrs.attributes) != len(output_attrs.attributes):
            return False, f"Attribute count mismatch: {len(source_attrs.attributes)} vs {len(output_attrs.attributes)}"
        
        # Check each attribute matches
        for out_attr in output_attrs.attributes:
            src_attr = source_attrs.get_by_name(out_attr.name)
            if not src_attr:
                # Output attribute not in source (added/modified)
                return False, f"Attribute '{out_attr.name}' modified or added"
            # Note: comparing values exactly is difficult due to type conversions
            # For now, we skip recompression only if attribute sets are identical
        
        # Check 5: No format overrides
        for ch in export_spec.output_channels:
            if ch.override_format:
                return False, "Output channel format override present"
        
        return True, "Can skip recompression: identical copy possible"

    def run(self) -> None:
        """Execute the export with parallel frame processing."""
        try:
            self._log("="*60)
            self._log("Starting EXR export...")
            self._log("="*60)

            # Ensure output directory exists before parallel export (avoid race conditions)
            output_dir = Path(self.export_spec.output_dir)
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                self._log(f"[DEBUG] Output directory created/verified: {output_dir.resolve()}")
            except Exception as e:
                self.signals.finished.emit(False, f"Could not create output directory: {e}")
                return

            # Log export configuration
            self._log(f"Output directory: {self.export_spec.output_dir}")
            self._log(f"Filename pattern: {self.export_spec.filename_pattern}")
            self._log(f"Target compression: {self.export_spec.compression}")
            self._log(f"Number of input sequences: {len(self.sequences)}")
            
            # Log compression for each sequence
            for seq_id, seq in self.sequences.items():
                if seq.static_probe and seq.static_probe.main_subimage:
                    src_compression = OiioAdapter.get_compression_from_probe(seq.static_probe, 0)
                    src_compression = src_compression.lower() if src_compression else "none"
                    self._log(f"  - {seq.display_name}: {len(seq.frames)} frames, compression: {src_compression}")

            # Validation
            self._log("\nValidating export configuration...")
            issues = ValidationEngine.validate_export(self.export_spec, self.sequences)

            errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
            warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]

            if errors:
                self._log(f"Validation errors: {len(errors)}")
                for issue in errors:
                    self._log(f"  ERROR: {issue}")
                self.signals.finished.emit(False, f"Export blocked: {len(errors)} validation errors")
                return

            if warnings:
                self._log(f"Validation warnings: {len(warnings)}")
                for issue in warnings:
                    self._log(f"  WARNING: {issue}")
            else:
                self._log("Validation: ✓ All checks passed")

            # Determine frame list to export
            frame_list = self._resolve_frame_list()
            if not frame_list:
                self.signals.finished.emit(False, "No frames to export")
                return

            self._log(f"\nFrame processing: {len(frame_list)} frames to export")
            if self.export_spec.frame_range:
                start, end = self.export_spec.frame_range
                self._log(f"  Frame range: {start} to {end}")
            
            # DEBUG: Show actual frame list summary
            if len(frame_list) <= 20:
                self._log(f"  Frames: {frame_list}")
            else:
                self._log(f"  Frames: {frame_list[:5]} ... {frame_list[-5:]} (showing first 5 and last 5)")

            # Check if we can skip recompression
            self._log("\nEvaluating compression optimization...")
            self._log(f"Compression policy: {self.compression_policy} mode")
            can_skip, reason = self.can_skip_recompression(
                self.export_spec, 
                self.sequences,
                self.compression_policy
            )
            if can_skip:
                self._log(f"✓ OPTIMIZATION ENABLED: {reason}")
                self._log("  Using direct copy (no decompression/recompression)")
                self._export_frames_direct_copy(frame_list)
            else:
                self._log(f"Standard export: {reason}")
                self._export_frames_parallel(frame_list)

        except Exception as e:
            self._log(f"FATAL: {e}")
            traceback.print_exc()
            self.signals.finished.emit(False, f"Export failed: {e}")

    def _export_frames_direct_copy(self, frame_list: List[int]) -> None:
        """
        Export frames via direct copy without decompression/recompression.
        Only used when compression matches and channels unchanged.
        Falls back to standard export if copy fails.
        """
        progress = AtomicProgress(len(frame_list))
        
        # Get source sequence (we know there's only one from can_skip_recompression)
        source_seq_id = self.export_spec.output_channels[0].source.sequence_id
        source_seq = self.sequences[source_seq_id]
        
        self._log("\n" + "-"*60)
        self._log("DIRECT COPY MODE (Optimization Enabled)")
        self._log("-"*60)
        self._log(f"Source sequence: {source_seq.display_name}")
        self._log(f"Total frames to process: {len(frame_list)}")
        if len(frame_list) <= 20:
            self._log(f"Frame list: {frame_list}")
        else:
            self._log(f"Frame list: {frame_list[:5]} ... {frame_list[-5:]} (first 5 and last 5)")
        self._log(f"Compression: {self.export_spec.compression} (no re-compression)")
        self._log(f"Output channels: {len(self.export_spec.output_channels)}")
        self._log("-"*60)

        try:
            for frame_num in frame_list:
                if self.stop_requested:
                    self._log("Export stopped by user")
                    self.signals.finished.emit(False, "Export stopped by user")
                    return

                try:
                    self._export_frame_direct_copy(frame_num, source_seq)
                    percent = progress.increment(frame_num)
                    self.signals.progress.emit(percent, f"Frame {frame_num} (direct copy)")
                except Exception as e:
                    # Log and fall back to standard export for remaining frames
                    self._log(f"\n⚠ WARNING: Direct copy failed for frame {frame_num}: {e}")
                    self._log(f"[DETAILS] Error type: {type(e).__name__}")
                    self._log("Falling back to standard parallel export for remaining frames...")
                    
                    # Export remaining frames using standard path
                    remaining_frames = [f for f in frame_list if f >= frame_num]
                    self._log(f"[DEBUG] Remaining frames to export: {len(remaining_frames)} frames (from frame {frame_num} onwards)")
                    self._export_frames_parallel(remaining_frames)
                    return

            # All frames completed successfully
            self._log("-"*60)
            self._log(f"✓ Export completed successfully (direct copy)!")
            self._log(f"Total frames exported: {len(frame_list)}")
            self._log(f"Compression format: {self.export_spec.compression}")
            self._log("-"*60)
            self.signals.finished.emit(True, "Export completed successfully!")

        except Exception as e:
            self._log(f"FATAL: Direct copy error: {e}")
            traceback.print_exc()
            self.signals.finished.emit(False, f"Export failed: {e}")

    def _export_frame_direct_copy(self, frame_num: int, source_seq: SequenceSpec) -> None:
        """
        Copy a single frame directly without decompression/recompression.
        Raises exception on failure (caller handles fallback).
        """
        # Build paths
        source_filename = source_seq.pattern.format(frame_num)
        source_path = source_seq.source_dir / source_filename
        
        if not source_path.exists():
            raise RuntimeError(f"Source file not found: {source_path}")

        output_path = Path(self.export_spec.output_dir) / self._format_filename(
            self.export_spec.filename_pattern, frame_num
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Open source file
            inp = oiio.ImageInput.open(str(source_path))
            if not inp:
                raise RuntimeError(f"Cannot open source: {source_path}")

            # Get spec from source
            src_spec = inp.spec()
            
            # Create output file
            out = oiio.ImageOutput.create(str(output_path))
            if not out:
                inp.close()
                raise RuntimeError(f"Cannot create output: {output_path}")

            # Open output with same spec as source
            if not out.open(str(output_path), src_spec):
                inp.close()
                out.close()
                raise RuntimeError(f"Cannot open output for writing: {output_path}")

            # Direct copy without decompression
            if not out.copy_image(inp):
                inp.close()
                out.close()
                raise RuntimeError(f"Failed to copy image data")

            inp.close()
            out.close()
            self._log(f"Wrote (direct copy): {output_path}")

        except Exception as e:
            # Ensure files are closed on error
            try:
                inp.close()
            except:
                pass
            try:
                out.close()
            except:
                pass
            raise

    def _export_frames_parallel(self, frame_list: List[int]) -> None:
        """Export frames in parallel using ThreadPoolExecutor."""
        num_workers = self._get_optimal_worker_count(len(frame_list))
        available_cores = os.cpu_count() or 4
        progress = AtomicProgress(len(frame_list))

        self._log("\n" + "-"*60)
        self._log("PARALLEL EXPORT MODE (Standard Processing)")
        self._log("-"*60)
        self._log(f"Total frames to export: {len(frame_list)}")
        self._log(f"Available CPU cores: {available_cores}")
        self._log(f"Frame-level worker threads: {num_workers}")
        self._log(f"Channel-level parallelization: ADAPTIVE (memory-aware)")
        self._log(f"  - Small frames (<5MP): up to 4 parallel channels")
        self._log(f"  - Medium frames (5-10MP): up to 3 parallel channels")
        self._log(f"  - Large frames (10-25MP): up to 2 parallel channels")
        self._log(f"  - Very large frames (>25MP): sequential channel reading")
        self._log(f"Compression: {self.export_spec.compression}")
        self._log(f"Output channels: {len(self.export_spec.output_channels)}")
        self._log(f"Processing mode: {'Decompression + Recompression' if num_workers > 1 else 'Single-threaded'}")
        self._log("-"*60)

        try:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Submit all frame export tasks
                futures = {
                    executor.submit(self._export_frame_wrapper, frame_num): frame_num
                    for frame_num in frame_list
                }

                # Process completions as they arrive, checking stop_requested regularly
                for future in as_completed(futures):
                    if self.stop_requested:
                        # Immediately terminate all workers
                        executor.shutdown(wait=False, cancel_futures=True)
                        self._log("Export stopped by user - terminating all workers")
                        self.signals.finished.emit(False, "Export stopped by user")
                        return

                    frame_num = futures[future]
                    try:
                        # Skip if future was cancelled
                        if future.cancelled():
                            continue

                        future.result()  # Will raise if exception occurred
                        percent = progress.increment(frame_num)
                        self.signals.progress.emit(percent, f"Frame {frame_num} (worker pool)")

                    except Exception as e:
                        # Check if error was due to user stop request
                        if self.stop_requested:
                            executor.shutdown(wait=False, cancel_futures=True)
                            self._log("Export stopped by user")
                            self.signals.finished.emit(False, "Export stopped by user")
                            return
                        
                        executor.shutdown(wait=False, cancel_futures=True)
                        self._log(f"ERROR exporting frame {frame_num}: {e}")
                        traceback.print_exc()
                        self.signals.finished.emit(False, f"Export failed at frame {frame_num}")
                        return

            # All frames completed successfully
            self._log("-"*60)
            self._log(f"✓ Export completed successfully!")
            self._log(f"Total frames exported: {len(frame_list)}")
            self._log(f"Worker threads used: {num_workers}")
            self._log(f"Compression format: {self.export_spec.compression}")
            self._log("-"*60)
            self.signals.finished.emit(True, "Export completed successfully!")

        except Exception as e:
            self._log(f"FATAL: Thread pool error: {e}")
            traceback.print_exc()
            self.signals.finished.emit(False, f"Export failed: {e}")

    def _export_frame_wrapper(self, frame_num: int) -> None:
        """
        Wrapper for frame export that can be used with ThreadPoolExecutor.
        Checks stop_requested flag and provides graceful cancellation.
        """
        # Check if stop was requested before starting
        if self.stop_requested:
            return

        # Export the frame, checking stop flag during processing
        try:
            self._export_frame(frame_num)
        except Exception:
            # If stop was requested during export, suppress the exception
            if self.stop_requested:
                return
            raise

    def _get_optimal_worker_count(self, num_frames: int) -> int:
        """
        Determine optimal number of worker threads.
        
        Strategy:
        - For small exports (<5 frames): 1 worker
        - For medium exports (5-100): min(4, available_cores)
        - For large exports (>100): min(8, available_cores)
        """
        available_cores = os.cpu_count() or 4

        if num_frames < 5:
            return 1
        elif num_frames < 100:
            return min(4, available_cores)
        else:
            return min(8, available_cores)

    def _resolve_frame_list(self) -> List[int]:
        """Determine which frames to export based on policy."""
        if not self.sequences:
            return []

        all_frames = []
        for seq in self.sequences.values():
            all_frames.extend(seq.frames)

        if not all_frames:
            return []

        all_frames = sorted(set(all_frames))

        # Apply frame_range filter if specified by user
        if self.export_spec.frame_range is not None:
            start_frame, end_frame = self.export_spec.frame_range
            all_frames = [f for f in all_frames if start_frame <= f <= end_frame]
            if not all_frames:
                self._log(
                    f"Warning: No frames found in range [{start_frame}, {end_frame}]"
                )

        return all_frames

    def _export_frame(self, frame_num: int) -> None:
        """Export a single frame with detailed compression and channel info."""
        # Check if stop was requested
        if self.stop_requested:
            raise RuntimeError("Export stopped by user")

        # Build output filename
        pattern = self.export_spec.filename_pattern
        output_path = Path(self.export_spec.output_dir) / self._format_filename(
            pattern, frame_num
        )

        # Read source channels in parallel (optimized)
        output_data, output_spec = self._assemble_frame(frame_num)
        if output_data is None:
            raise RuntimeError(f"Failed to assemble frame {frame_num}")

        # Check again before writing (I/O operations may have taken time)
        if self.stop_requested:
            raise RuntimeError("Export stopped by user")

        # Write output EXR
        self._write_exr(output_path, output_data, output_spec)
        
        # Log detailed information about written frame
        channel_names = ", ".join(output_spec.get("channels", []))
        resolution = f"{output_spec.get('width', '?')}x{output_spec.get('height', '?')}"
        num_channels = len(output_spec.get('channels', []))
        self._log(f"  Frame {frame_num}: {resolution} | {num_channels} channels (parallel read: {channel_names}) | compression: {self.export_spec.compression}")


    def _format_filename(self, pattern: str, frame: int) -> str:
        """Format filename with frame number."""
        import re
        result = pattern
        result = re.sub(r"%0(\d+)d", lambda m: str(frame).zfill(int(m.group(1))), result)
        result = re.sub(r"#+", lambda m: str(frame).zfill(len(m.group(0))), result)
        return result

    def _assemble_frame(self, frame_num: int) -> tuple[Optional[np.ndarray], dict]:
        """
        Assemble output frame from selected input channels.
        
        Optimized to read channels in parallel from same source files.
        Channels from different files are grouped and read in parallel batches.

        Returns (pixel_data, spec_dict) or (None, {}) if failed.
        """
        if not self.export_spec.output_channels:
            return None, {}

        # Use first output channel to determine resolution
        first_ch = self.export_spec.output_channels[0]
        first_seq = self.sequences.get(first_ch.source.sequence_id)
        if not first_seq or not first_seq.static_probe:
            return None, {}

        if not first_seq.static_probe.main_subimage:
            return None, {}

        spec = first_seq.static_probe.main_subimage.spec
        width, height = spec.width, spec.height

        # Allocate output buffer (float32 for now; could be more flexible)
        n_output_channels = len(self.export_spec.output_channels)
        output_data = np.zeros((height, width, n_output_channels), dtype=np.float32)

        # Check for stop request before starting channel reads
        if self.stop_requested:
            raise RuntimeError("Export stopped by user")

        # Group channels by source file for efficient parallel reading
        channels_by_source = {}  # (sequence_id, frame_path) -> [(out_idx, channel_spec), ...]
        
        for out_idx, out_ch in enumerate(self.export_spec.output_channels):
            src_seq = self.sequences.get(out_ch.source.sequence_id)
            if not src_seq:
                continue

            # Get full frame path
            filename = src_seq.pattern.format(frame_num)
            frame_path = src_seq.source_dir / filename
            if not frame_path.exists():
                self._log(f"Warning: Source file not found: {frame_path}")
                continue

            key = (out_ch.source.sequence_id, str(frame_path))
            if key not in channels_by_source:
                channels_by_source[key] = []
            channels_by_source[key].append((out_idx, out_ch))

        # Read channels in parallel batches (channels from same file in parallel)
        # For each source file, use ThreadPoolExecutor to read all channels from that file in parallel
        for source_key, channel_list in channels_by_source.items():
            if self.stop_requested:
                raise RuntimeError("Export stopped by user")

            seq_id, frame_path = source_key
            
            # Read all channels from this file in parallel (with memory-aware limits)
            try:
                results = self._read_channels_parallel_from_file(
                    frame_path,
                    channel_list,
                    frame_resolution=(width, height)
                )
                
                # Populate output buffer with results
                for (out_idx, out_ch), src_data in zip(channel_list, results):
                    if src_data is not None:
                        output_data[:, :, out_idx] = src_data
                    
            except Exception as e:
                # Suppress exception if stop was requested
                if self.stop_requested:
                    raise RuntimeError("Export stopped by user")
                self._log(f"Warning: Could not read channels from {frame_path}: {e}")

        return output_data, {
            "width": width,
            "height": height,
            "channels": [ch.output_name for ch in self.export_spec.output_channels],
        }

    def _read_channels_parallel_from_file(
        self, filepath: str, channel_specs: List[tuple[int, any]], frame_resolution: tuple[int, int] = None
    ) -> List[Optional[np.ndarray]]:
        """
        Read multiple channels from the same file with memory-aware parallelization.
        
        For large frames, automatically falls back to sequential reading to avoid
        memory exhaustion from simultaneous large buffer allocations.
        
        Args:
            filepath: Path to source file
            channel_specs: List of (out_idx, channel_spec) tuples
            frame_resolution: (width, height) tuple for memory estimation
        
        Returns:
            List of numpy arrays in same order as channel_specs, or None for each failed read
        """
        if not channel_specs:
            return []

        results = [None] * len(channel_specs)
        
        # If only one channel, read directly without threading overhead
        if len(channel_specs) == 1:
            out_idx, out_ch = channel_specs[0]
            try:
                data = self._read_channel_from_file(
                    filepath,
                    out_ch.source.channel_name,
                    out_ch.source.subimage_index,
                )
                results[0] = data
            except Exception:
                pass
            return results

        # Estimate memory usage per parallel read
        # Each channel read = width × height × 4 bytes (float32)
        num_workers = self._calculate_optimal_channel_workers(len(channel_specs), frame_resolution)
        
        if num_workers <= 1:
            # Sequential reading for large frames
            for idx, (out_idx, out_ch) in enumerate(channel_specs):
                try:
                    results[idx] = self._read_channel_from_file(
                        filepath,
                        out_ch.source.channel_name,
                        out_ch.source.subimage_index,
                    )
                except Exception as e:
                    if not self.stop_requested:
                        pass  # Silently handle, will be logged elsewhere
        else:
            # Use ThreadPoolExecutor for parallel channel reads from same file
            try:
                with ThreadPoolExecutor(max_workers=num_workers) as executor:
                    futures = []
                    
                    for idx, (out_idx, out_ch) in enumerate(channel_specs):
                        future = executor.submit(
                            self._read_channel_from_file,
                            filepath,
                            out_ch.source.channel_name,
                            out_ch.source.subimage_index,
                        )
                        futures.append((idx, future))
                    
                    # Collect results
                    for idx, future in futures:
                        try:
                            results[idx] = future.result()
                        except Exception as e:
                            if not self.stop_requested:
                                pass  # Silently handle
            
            except Exception as e:
                # Fall back to sequential reading on any error
                for idx, (out_idx, out_ch) in enumerate(channel_specs):
                    try:
                        results[idx] = self._read_channel_from_file(
                            filepath,
                            out_ch.source.channel_name,
                            out_ch.source.subimage_index,
                        )
                    except Exception:
                        pass

        return results

    def _calculate_optimal_channel_workers(self, num_channels: int, frame_resolution: tuple[int, int] = None) -> int:
        """
        Calculate optimal number of parallel channel readers based on memory constraints.
        
        For large frames, reduces parallelism to avoid memory exhaustion.
        
        Args:
            num_channels: Number of channels to read
            frame_resolution: (width, height) tuple or None
        
        Returns:
            Number of worker threads (1 = sequential)
        """
        # Default resolution if not provided
        if frame_resolution is None:
            width, height = 2048, 1080
        else:
            width, height = frame_resolution
        
        # Estimate bytes per channel: width × height × 4 (float32)
        bytes_per_channel = width * height * 4
        
        # Memory thresholds
        # Large frame = > 10 million pixels (40+ MB per channel)
        # Very large frame = > 25 million pixels (100+ MB per channel)
        pixels = width * height
        
        if pixels > 25_000_000:
            # Very large frames (> 100MB per channel) - sequential only
            return 1
        elif pixels > 10_000_000:
            # Large frames (40-100MB per channel) - max 2 parallel
            return min(2, num_channels)
        elif pixels > 5_000_000:
            # Medium frames (20-40MB per channel) - max 3 parallel
            return min(3, num_channels)
        else:
            # Small frames - up to 4 parallel (original behavior)
            return min(4, num_channels)

    def _read_channel_from_file(
        self, filepath: str, channel_name: str, subimage_index: int = 0
    ) -> Optional[np.ndarray]:
        """
        Read a single channel from a file (thread-safe).
        
        This method is designed to be called from multiple threads reading
        different channels from the same file. Each thread opens its own
        file handle to avoid synchronization overhead.
        """
        # Check for stop request before I/O
        if self.stop_requested:
            raise RuntimeError("Export stopped by user")

        try:
            inp = oiio.ImageInput.open(filepath)
            if not inp:
                return None

            # Seek to subimage if needed
            if subimage_index > 0:
                if not inp.seek_subimage(subimage_index, 0):
                    inp.close()
                    return None

            spec = inp.spec()
            width, height = spec.width, spec.height

            # Find channel index
            ch_idx = None
            for i, name in enumerate(spec.channelnames):
                if name == channel_name:
                    ch_idx = i
                    break

            if ch_idx is None:
                inp.close()
                return None

            # Read all pixels (simple approach)
            pixels = inp.read_image()
            inp.close()

            if pixels is None:
                return None

            # Extract channel and reshape
            # pixels is typically (height, width, channels)
            if isinstance(pixels, np.ndarray):
                channel_data = pixels[:, :, ch_idx].astype(np.float32)
                return channel_data

            return None

        except Exception as e:
            # Only log if not due to stop request
            if not self.stop_requested:
                self._log(f"Error reading channel: {e}")
            return None

    def _write_exr(self, output_path: Path, pixel_data: np.ndarray, spec_dict: dict) -> None:
        """Write output EXR file (thread-safe).
        
        Uses a lock to serialize OIIO operations since OIIO may not be thread-safe.
        """
        out = None
        try:
            # Convert to absolute path to avoid any issues with relative paths
            output_path = Path(output_path).resolve()
            output_dir = output_path.parent
            
            # Verify directory exists (should have been created by run())
            if not output_dir.exists():
                raise RuntimeError(f"Output directory missing: {output_dir}")

            # Create output spec
            out_spec = oiio.ImageSpec(
                spec_dict["width"],
                spec_dict["height"],
                len(spec_dict["channels"]),
                oiio.FLOAT,
            )
            out_spec.channelnames = spec_dict["channels"]

            # Apply export attributes (silently skip on error)
            for attr in self.export_spec.output_attributes.attributes:
                try:
                    value = attr.value
                    if isinstance(value, (tuple, list)):
                        value = " ".join(str(v) for v in value)
                    out_spec.attribute(attr.name, value)
                except Exception:
                    pass

            # Set compression (silently skip on error)
            try:
                out_spec.attribute("compression", self.export_spec.compression)
            except Exception:
                pass

            # Use lock to serialize OIIO operations (OIIO may not be thread-safe)
            with ExportRunner._oiio_lock:
                # Convert to absolute path with forward slashes for OIIO
                output_path_str = str(output_path).replace("\\", "/")
                
                # Create output with OIIO
                out = oiio.ImageOutput.create(output_path_str)
                if not out:
                    raise RuntimeError("ImageOutput.create failed")

                # Open for writing
                if not out.open(output_path_str, out_spec):
                    # Get OIIO error message
                    error_msg = out.geterror() if hasattr(out, 'geterror') else "unknown error"
                    raise RuntimeError(f"out.open failed: OIIO error: {error_msg}")

                # Write image data
                if not out.write_image(pixel_data):
                    error_msg = out.geterror() if hasattr(out, 'geterror') else "unknown error"
                    raise RuntimeError(f"write_image failed: OIIO error: {error_msg}")

                out.close()
                out = None
                
        except Exception as e:
            raise RuntimeError(f"Write failed for {output_path}: {e}")
        finally:
            # Ensure output object is closed
            if out:
                try:
                    out.close()
                except Exception:
                    pass

    def _log(self, message: str) -> None:
        """Emit a log message."""
        self.signals.log.emit(message)


class ExportManager(QObject):
    """Manages export thread pool."""

    finished = Signal(bool, str)  # (success, message)
    log = Signal(str)
    progress = Signal(int, str)  # (percent, message)

    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool()
        self.current_runner: Optional[ExportRunner] = None

    def start_export(
        self,
        export_spec: ExportSpec,
        sequences: dict[str, SequenceSpec],
        compression_policy: str = "skip",
    ) -> None:
        """Start an export in a worker thread.
        
        Args:
            export_spec: Export configuration
            sequences: Available sequences
            compression_policy: 'skip' or 'always' for compression handling
        """
        if self.current_runner:
            self.log.emit("Export already in progress")
            return

        self.current_runner = ExportRunner(export_spec, sequences, compression_policy)
        self.current_runner.signals.finished.connect(self._on_finished)
        self.current_runner.signals.log.connect(self.log.emit)
        self.current_runner.signals.progress.connect(self.progress.emit)

        self.thread_pool.start(self.current_runner)

    def stop_export(self) -> None:
        """Request the current export to stop."""
        if self.current_runner:
            self.current_runner.request_stop()

    def _on_finished(self, success: bool, message: str) -> None:
        """Handle export completion."""
        self.current_runner = None
        self.finished.emit(success, message)
