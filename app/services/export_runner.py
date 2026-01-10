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

    def __init__(
        self,
        export_spec: ExportSpec,
        sequences: dict[str, SequenceSpec],
    ):
        super().__init__()
        self.export_spec = export_spec
        self.sequences = sequences
        self.signals = ExportSignals()
        self.stop_requested = False  # Flag to stop export

    def request_stop(self) -> None:
        """Request the export to stop gracefully."""
        self.stop_requested = True

    def run(self) -> None:
        """Execute the export with parallel frame processing."""
        try:
            self._log("Starting export...")

            # Validation
            self._log("Validating export configuration...")
            issues = ValidationEngine.validate_export(self.export_spec, self.sequences)

            errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
            warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]

            if errors:
                for issue in errors:
                    self._log(f"ERROR: {issue}")
                self.signals.finished.emit(False, f"Export blocked: {len(errors)} validation errors")
                return

            for issue in warnings:
                self._log(f"WARNING: {issue}")

            # Determine frame list to export
            frame_list = self._resolve_frame_list()
            if not frame_list:
                self.signals.finished.emit(False, "No frames to export")
                return

            self._log(f"Exporting {len(frame_list)} frames...")

            # Export frames in parallel
            self._export_frames_parallel(frame_list)

        except Exception as e:
            self._log(f"FATAL: {e}")
            traceback.print_exc()
            self.signals.finished.emit(False, f"Export failed: {e}")

    def _export_frames_parallel(self, frame_list: List[int]) -> None:
        """Export frames in parallel using ThreadPoolExecutor."""
        num_workers = self._get_optimal_worker_count(len(frame_list))
        progress = AtomicProgress(len(frame_list))

        self._log(f"Using {num_workers} worker threads")

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
                        self.signals.progress.emit(percent, f"Frame {frame_num}")

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
            self._log("Export completed successfully!")
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
        """Export a single frame."""
        # Check if stop was requested
        if self.stop_requested:
            raise RuntimeError("Export stopped by user")

        # Build output filename
        pattern = self.export_spec.filename_pattern
        output_path = Path(self.export_spec.output_dir) / self._format_filename(
            pattern, frame_num
        )

        # Read source channels and build output buffer
        output_data, output_spec = self._assemble_frame(frame_num)
        if output_data is None:
            raise RuntimeError(f"Failed to assemble frame {frame_num}")

        # Check again before writing (I/O operations may have taken time)
        if self.stop_requested:
            raise RuntimeError("Export stopped by user")

        # Write output EXR
        self._write_exr(output_path, output_data, output_spec)
        self._log(f"Wrote: {output_path}")

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

        # Fill output buffer
        for out_idx, out_ch in enumerate(self.export_spec.output_channels):
            # Check for stop request between channel reads
            if self.stop_requested:
                raise RuntimeError("Export stopped by user")

            src_seq = self.sequences.get(out_ch.source.sequence_id)
            if not src_seq:
                continue

            # Get full frame path (source_dir + formatted filename)
            filename = src_seq.pattern.format(frame_num)
            frame_path = src_seq.source_dir / filename
            if not frame_path.exists():
                self._log(f"Warning: Source file not found: {frame_path}")
                continue

            # Read source channel
            try:
                src_data = self._read_channel_from_file(
                    str(frame_path),
                    out_ch.source.channel_name,
                    out_ch.source.subimage_index,
                )
                if src_data is not None:
                    output_data[:, :, out_idx] = src_data
            except Exception as e:
                # Suppress exception if stop was requested
                if self.stop_requested:
                    raise RuntimeError("Export stopped by user")
                self._log(f"Warning: Could not read {out_ch.source.channel_name}: {e}")

        return output_data, {
            "width": width,
            "height": height,
            "channels": [ch.output_name for ch in self.export_spec.output_channels],
        }

    def _read_channel_from_file(
        self, filepath: str, channel_name: str, subimage_index: int = 0
    ) -> Optional[np.ndarray]:
        """Read a single channel from a file."""
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
            self._log(f"Error reading channel: {e}")
            return None

    def _write_exr(self, output_path: Path, pixel_data: np.ndarray, spec_dict: dict) -> None:
        """Write output EXR file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create output spec
        out_spec = oiio.ImageSpec(
            spec_dict["width"],
            spec_dict["height"],
            len(spec_dict["channels"]),
            oiio.FLOAT,
        )
        out_spec.channelnames = spec_dict["channels"]

        # Apply export attributes
        for attr in self.export_spec.output_attributes.attributes:
            try:
                # Handle array/tuple attributes by converting to string
                value = attr.value
                if isinstance(value, (tuple, list)):
                    # Convert tuple/list to space-separated string
                    value = " ".join(str(v) for v in value)
                out_spec.attribute(attr.name, value)
            except Exception as e:
                self._log(f"Warning: Could not set attribute '{attr.name}': {e}")

        # Set compression
        try:
            out_spec.attribute("compression", self.export_spec.compression)
        except Exception as e:
            self._log(f"Warning: Could not set compression: {e}")

        # Write file
        out = oiio.ImageOutput.create(str(output_path))
        if not out:
            raise RuntimeError(f"Could not create output file: {output_path}")

        # Transpose pixel data for OIIO (expects height x width x channels)
        if not out.open(str(output_path), out_spec):
            raise RuntimeError(f"Could not open output file for writing: {output_path}")

        if not out.write_image(pixel_data):
            out.close()
            raise RuntimeError(f"Failed to write image: {output_path}")

        out.close()

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
    ) -> None:
        """Start an export in a worker thread."""
        if self.current_runner:
            self.log.emit("Export already in progress")
            return

        self.current_runner = ExportRunner(export_spec, sequences)
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
