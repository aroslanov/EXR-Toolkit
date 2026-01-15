"""
Validation engine for EXR export.

Structured validation rules that must pass before export.
Returns ValidationIssue list; ERROR severity blocks export.
"""

from typing import List
from pathlib import Path

from ..core import (
    ExportSpec,
    ValidationIssue,
    ValidationSeverity,
    SequenceSpec,
)


class ValidationEngine:
    """Validates export configurations."""

    @staticmethod
    def validate_export(
        export_spec: ExportSpec,
        sequences: dict[str, SequenceSpec],
    ) -> List[ValidationIssue]:
        """
        Validate export spec and sequences.

        Returns list of ValidationIssue; export is blocked if any ERROR present.
        """
        issues = []

        # 1. Output channels validation
        issues.extend(ValidationEngine._validate_output_channels(export_spec))

        # 2. Channel format compatibility
        issues.extend(
            ValidationEngine._validate_channel_formats(export_spec, sequences)
        )

        # 3. Export path validation
        issues.extend(ValidationEngine._validate_export_path(export_spec))

        # 4. Sequence policy validation
        issues.extend(
            ValidationEngine._validate_sequence_policy(export_spec, sequences)
        )

        # 5. Attributes validation
        issues.extend(ValidationEngine._validate_attributes(export_spec))

        return issues

    @staticmethod
    def _validate_output_channels(export_spec: ExportSpec) -> List[ValidationIssue]:
        """Validate output channel configuration."""
        issues = []

        # At least one output channel
        if not export_spec.output_channels:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="NO_OUTPUT_CHANNELS",
                    message="At least one output channel must be selected.",
                    context={},
                )
            )
            return issues

        # Unique channel names
        names = [ch.output_name for ch in export_spec.output_channels]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="DUPLICATE_CHANNEL_NAMES",
                    message=f"Duplicate output channel names: {set(duplicates)}",
                    context={"duplicates": list(set(duplicates))},
                )
            )

        # All channels have valid source references
        for ch in export_spec.output_channels:
            if not ch.source:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="MISSING_CHANNEL_SOURCE",
                        message=f"Output channel '{ch.output_name}' has no source reference.",
                        context={"channel_name": ch.output_name},
                    )
                )

        return issues

    @staticmethod
    def _validate_channel_formats(
        export_spec: ExportSpec,
        sequences: dict[str, SequenceSpec],
    ) -> List[ValidationIssue]:
        """Validate channel format compatibility."""
        issues = []

        # All output channels must have consistent resolution
        # (unless resize is enabled to normalize inputs)
        from ..core import ResizePolicy
        
        resolutions = set()
        for ch in export_spec.output_channels:
            if not ch.source:
                continue

            seq = sequences.get(ch.source.sequence_id)
            if not seq or not seq.static_probe:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="MISSING_SEQUENCE",
                        message=f"Sequence '{ch.source.sequence_id}' not found.",
                        context={"sequence_id": ch.source.sequence_id},
                    )
                )
                continue

            spec = seq.static_probe.main_subimage
            if spec:
                resolutions.add((spec.spec.width, spec.spec.height))

        # Only enforce resolution consistency if resize is disabled
        if len(resolutions) > 1 and export_spec.resize_spec.policy == ResizePolicy.NONE:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="INCONSISTENT_RESOLUTION",
                    message=f"Output channels have different resolutions: {resolutions}",
                    context={"resolutions": list(resolutions)},
                )
            )

        # No implicit type conversions (phase-1 strict)
        for ch in export_spec.output_channels:
            if not ch.source or ch.override_format:
                # Override allowed; skip check
                continue

            seq = sequences.get(ch.source.sequence_id)
            if not seq or not seq.static_probe:
                continue

            src_channel = _find_channel_in_probe(
                seq.static_probe,
                ch.source.channel_name,
                ch.source.subimage_index,
            )
            if not src_channel:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="SOURCE_CHANNEL_NOT_FOUND",
                        message=f"Channel '{ch.source.channel_name}' not found in sequence '{ch.source.sequence_id}'.",
                        context={
                            "sequence_id": ch.source.sequence_id,
                            "channel_name": ch.source.channel_name,
                        },
                    )
                )

        return issues

    @staticmethod
    def _validate_export_path(export_spec: ExportSpec) -> List[ValidationIssue]:
        """Validate output path and filename pattern."""
        issues = []

        if not export_spec.output_dir:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_OUTPUT_DIR",
                    message="Output directory not specified.",
                    context={},
                )
            )
            return issues

        output_path = Path(export_spec.output_dir)
        if not output_path.exists():
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="CANNOT_CREATE_OUTPUT_DIR",
                        message=f"Cannot create output directory: {e}",
                        context={"error": str(e)},
                    )
                )

        # Filename pattern must include frame token
        pattern = export_spec.filename_pattern
        if "%04d" not in pattern and "####" not in pattern:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="NO_FRAME_TOKEN",
                    message="Filename pattern has no frame token (%04d or ####). Will overwrite same file for each frame.",
                    context={"pattern": pattern},
                )
            )

        return issues

    @staticmethod
    def _validate_sequence_policy(
        export_spec: ExportSpec,
        sequences: dict[str, SequenceSpec],
    ) -> List[ValidationIssue]:
        """Validate frame range policy."""
        issues = []

        if not export_spec.frame_policy:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="NO_FRAME_POLICY",
                    message="Frame range policy not selected.",
                    context={},
                )
            )

        # Warn if sequences have different lengths
        frame_counts = {}
        for seq in sequences.values():
            frame_counts[seq.id] = len(seq.frames)

        if len(set(frame_counts.values())) > 1:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="SEQUENCE_LENGTH_MISMATCH",
                    message=f"Sequences have different frame counts: {frame_counts}. Frame policy: {export_spec.frame_policy.name}",
                    context={"frame_counts": frame_counts},
                )
            )

        return issues

    @staticmethod
    def _validate_attributes(export_spec: ExportSpec) -> List[ValidationIssue]:
        """Validate output attributes."""
        issues = []

        # Check for obviously invalid attribute types
        for attr in export_spec.output_attributes.attributes:
            if not attr.name:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="EMPTY_ATTRIBUTE_NAME",
                        message="Attribute has empty name.",
                        context={},
                    )
                )

            if attr.value is None and attr.editable:
                # Warn about None values (may be okay depending on OIIO semantics)
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="NULL_ATTRIBUTE_VALUE",
                        message=f"Attribute '{attr.name}' has None value.",
                        context={"attribute_name": attr.name},
                    )
                )

        return issues


def _find_channel_in_probe(probe, channel_name: str, subimage_index: int):
    """Find a channel in a FileProbe by name and subimage."""
    if subimage_index >= len(probe.subimages):
        return None
    subimage = probe.subimages[subimage_index]
    for ch in subimage.channels:
        if ch.name == channel_name:
            return ch
    return None
