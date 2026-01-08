"""Tests for PDK version mismatch detection and reporting."""

import pytest

from src.controller.pdk_version import (
    PDKVersion,
    PDKVersionMismatch,
    compare_pdk_versions,
    detect_pdk_version_mismatch,
    format_pdk_version_mismatch_warning,
)


class TestPDKVersion:
    """Tests for PDKVersion dataclass."""

    def test_create_pdk_version_minimal(self) -> None:
        """Test creating PDK version with only name."""
        pdk = PDKVersion(pdk_name="nangate45")
        assert pdk.pdk_name == "nangate45"
        assert pdk.version is None
        assert pdk.variant is None
        assert pdk.source is None

    def test_create_pdk_version_full(self) -> None:
        """Test creating PDK version with all fields."""
        pdk = PDKVersion(
            pdk_name="sky130",
            version="fd-sc-hd",
            variant="sky130A",
            source="container",
            metadata={"path": "/pdk/sky130A"},
        )
        assert pdk.pdk_name == "sky130"
        assert pdk.version == "fd-sc-hd"
        assert pdk.variant == "sky130A"
        assert pdk.source == "container"
        assert pdk.metadata == {"path": "/pdk/sky130A"}

    def test_pdk_name_normalized_to_lowercase(self) -> None:
        """Test PDK name is normalized to lowercase for comparison."""
        pdk1 = PDKVersion(pdk_name="NANGATE45")
        pdk2 = PDKVersion(pdk_name="Nangate45")
        pdk3 = PDKVersion(pdk_name="nangate45")
        assert pdk1.pdk_name == "nangate45"
        assert pdk2.pdk_name == "nangate45"
        assert pdk3.pdk_name == "nangate45"

    def test_pdk_version_to_dict(self) -> None:
        """Test PDKVersion serialization to dict."""
        pdk = PDKVersion(
            pdk_name="asap7",
            version="r1p7",
            variant="7t",
            source="snapshot",
        )
        result = pdk.to_dict()
        assert result == {
            "pdk_name": "asap7",
            "version": "r1p7",
            "variant": "7t",
            "source": "snapshot",
            "metadata": {},
        }

    def test_pdk_version_str_full(self) -> None:
        """Test human-readable PDK version string."""
        pdk = PDKVersion(pdk_name="sky130", version="fd-sc-hd", variant="sky130A")
        assert str(pdk) == "sky130 sky130A vfd-sc-hd"

    def test_pdk_version_str_minimal(self) -> None:
        """Test human-readable string with only name."""
        pdk = PDKVersion(pdk_name="nangate45")
        assert str(pdk) == "nangate45"


class TestComparePDKVersions:
    """Tests for PDK version comparison logic."""

    def test_identical_pdks_are_compatible(self) -> None:
        """Test identical PDK versions are compatible."""
        pdk1 = PDKVersion(pdk_name="nangate45", version="1.0")
        pdk2 = PDKVersion(pdk_name="nangate45", version="1.0")
        compatible, message = compare_pdk_versions(pdk1, pdk2)
        assert compatible is True
        assert message is None

    def test_different_pdk_names_incompatible(self) -> None:
        """Test different PDK names are incompatible."""
        pdk1 = PDKVersion(pdk_name="nangate45")
        pdk2 = PDKVersion(pdk_name="asap7")
        compatible, message = compare_pdk_versions(pdk1, pdk2)
        assert compatible is False
        assert "PDK name mismatch" in message
        assert "nangate45" in message
        assert "asap7" in message

    def test_case_insensitive_pdk_name_comparison(self) -> None:
        """Test PDK name comparison is case-insensitive."""
        pdk1 = PDKVersion(pdk_name="NANGATE45")
        pdk2 = PDKVersion(pdk_name="nangate45")
        compatible, message = compare_pdk_versions(pdk1, pdk2)
        assert compatible is True
        assert message is None

    def test_different_versions_incompatible(self) -> None:
        """Test different versions are incompatible."""
        pdk1 = PDKVersion(pdk_name="sky130", version="fd-sc-hd")
        pdk2 = PDKVersion(pdk_name="sky130", version="fd-sc-hs")
        compatible, message = compare_pdk_versions(pdk1, pdk2)
        assert compatible is False
        assert "PDK version mismatch" in message
        assert "fd-sc-hd" in message
        assert "fd-sc-hs" in message

    def test_different_variants_incompatible(self) -> None:
        """Test different variants are incompatible."""
        pdk1 = PDKVersion(pdk_name="sky130", variant="sky130A")
        pdk2 = PDKVersion(pdk_name="sky130", variant="sky130B")
        compatible, message = compare_pdk_versions(pdk1, pdk2)
        assert compatible is False
        assert "PDK variant mismatch" in message
        assert "sky130A" in message
        assert "sky130B" in message

    def test_missing_version_in_one_pdk_compatible(self) -> None:
        """Test PDKs with missing version in one are compatible."""
        # If one doesn't specify version, we can't compare - assume compatible
        pdk1 = PDKVersion(pdk_name="nangate45", version="1.0")
        pdk2 = PDKVersion(pdk_name="nangate45")
        compatible, message = compare_pdk_versions(pdk1, pdk2)
        assert compatible is True
        assert message is None

    def test_missing_variant_in_one_pdk_compatible(self) -> None:
        """Test PDKs with missing variant in one are compatible."""
        pdk1 = PDKVersion(pdk_name="sky130", variant="sky130A")
        pdk2 = PDKVersion(pdk_name="sky130")
        compatible, message = compare_pdk_versions(pdk1, pdk2)
        assert compatible is True
        assert message is None


class TestDetectPDKVersionMismatch:
    """Tests for PDK version mismatch detection."""

    def test_compatible_pdks_no_mismatch(self) -> None:
        """Test no mismatch detected for compatible PDKs."""
        snapshot_pdk = PDKVersion(pdk_name="nangate45", version="1.0", source="snapshot")
        runtime_pdk = PDKVersion(pdk_name="nangate45", version="1.0", source="container")
        mismatch = detect_pdk_version_mismatch(snapshot_pdk, runtime_pdk)
        assert mismatch is None

    def test_incompatible_pdks_detects_mismatch(self) -> None:
        """Test mismatch detected for incompatible PDKs."""
        snapshot_pdk = PDKVersion(pdk_name="nangate45", version="1.0", source="snapshot")
        runtime_pdk = PDKVersion(pdk_name="nangate45", version="2.0", source="container")
        mismatch = detect_pdk_version_mismatch(snapshot_pdk, runtime_pdk)
        assert mismatch is not None
        assert mismatch.snapshot_pdk == snapshot_pdk
        assert mismatch.runtime_pdk == runtime_pdk
        assert mismatch.severity == "error"
        assert "mismatch" in mismatch.message.lower()

    def test_missing_snapshot_pdk_no_mismatch(self) -> None:
        """Test no mismatch when snapshot PDK not recorded."""
        runtime_pdk = PDKVersion(pdk_name="nangate45", version="1.0")
        mismatch = detect_pdk_version_mismatch(None, runtime_pdk)
        assert mismatch is None

    def test_missing_runtime_pdk_no_mismatch(self) -> None:
        """Test no mismatch when runtime PDK not detected."""
        snapshot_pdk = PDKVersion(pdk_name="nangate45", version="1.0")
        mismatch = detect_pdk_version_mismatch(snapshot_pdk, None)
        assert mismatch is None

    def test_both_pdks_missing_no_mismatch(self) -> None:
        """Test no mismatch when both PDK versions unknown."""
        mismatch = detect_pdk_version_mismatch(None, None)
        assert mismatch is None

    def test_different_pdk_names_creates_mismatch(self) -> None:
        """Test mismatch created for different PDK names."""
        snapshot_pdk = PDKVersion(pdk_name="nangate45", source="snapshot")
        runtime_pdk = PDKVersion(pdk_name="asap7", source="container")
        mismatch = detect_pdk_version_mismatch(snapshot_pdk, runtime_pdk)
        assert mismatch is not None
        assert "nangate45" in mismatch.message
        assert "asap7" in mismatch.message


class TestPDKVersionMismatch:
    """Tests for PDKVersionMismatch dataclass."""

    def test_create_mismatch_with_message(self) -> None:
        """Test creating mismatch with custom message."""
        snapshot_pdk = PDKVersion(pdk_name="sky130", version="A")
        runtime_pdk = PDKVersion(pdk_name="sky130", version="B")
        mismatch = PDKVersionMismatch(
            snapshot_pdk=snapshot_pdk,
            runtime_pdk=runtime_pdk,
            severity="warning",
            message="Custom warning message",
        )
        assert mismatch.message == "Custom warning message"
        assert mismatch.severity == "warning"

    def test_create_mismatch_auto_message(self) -> None:
        """Test automatic message generation."""
        snapshot_pdk = PDKVersion(pdk_name="nangate45", version="1.0")
        runtime_pdk = PDKVersion(pdk_name="nangate45", version="2.0")
        mismatch = PDKVersionMismatch(
            snapshot_pdk=snapshot_pdk,
            runtime_pdk=runtime_pdk,
        )
        # Should auto-generate message
        assert "mismatch" in mismatch.message.lower()
        assert "nangate45" in mismatch.message

    def test_mismatch_to_dict(self) -> None:
        """Test mismatch serialization to dict."""
        snapshot_pdk = PDKVersion(pdk_name="asap7", version="r1p7")
        runtime_pdk = PDKVersion(pdk_name="asap7", version="r1p8")
        mismatch = PDKVersionMismatch(
            snapshot_pdk=snapshot_pdk,
            runtime_pdk=runtime_pdk,
            severity="error",
            message="Version mismatch",
        )
        result = mismatch.to_dict()
        assert result["severity"] == "error"
        assert result["message"] == "Version mismatch"
        assert result["snapshot_pdk"]["pdk_name"] == "asap7"
        assert result["runtime_pdk"]["pdk_name"] == "asap7"


class TestFormatPDKVersionMismatchWarning:
    """Tests for PDK mismatch warning formatting."""

    def test_format_warning_includes_both_pdks(self) -> None:
        """Test formatted warning includes both snapshot and runtime PDK info."""
        snapshot_pdk = PDKVersion(
            pdk_name="sky130",
            version="fd-sc-hd",
            variant="sky130A",
            source="snapshot",
        )
        runtime_pdk = PDKVersion(
            pdk_name="sky130",
            version="fd-sc-hs",
            variant="sky130B",
            source="container",
        )
        mismatch = PDKVersionMismatch(
            snapshot_pdk=snapshot_pdk,
            runtime_pdk=runtime_pdk,
            message="Version and variant mismatch",
        )

        warning = format_pdk_version_mismatch_warning(mismatch)

        # Check both PDKs are in warning
        assert "sky130" in warning
        assert "fd-sc-hd" in warning
        assert "fd-sc-hs" in warning
        assert "sky130A" in warning
        assert "sky130B" in warning
        assert "snapshot" in warning
        assert "container" in warning

    def test_format_warning_includes_recommendation(self) -> None:
        """Test formatted warning includes recommendation."""
        snapshot_pdk = PDKVersion(pdk_name="nangate45", version="1.0")
        runtime_pdk = PDKVersion(pdk_name="nangate45", version="2.0")
        mismatch = PDKVersionMismatch(
            snapshot_pdk=snapshot_pdk,
            runtime_pdk=runtime_pdk,
        )

        warning = format_pdk_version_mismatch_warning(mismatch)

        # Should include recommendations
        assert "RECOMMENDATION" in warning
        assert "Rebuild snapshot" in warning or "rebuild snapshot" in warning.lower()

    def test_format_warning_includes_separator_lines(self) -> None:
        """Test formatted warning has clear visual separation."""
        snapshot_pdk = PDKVersion(pdk_name="asap7")
        runtime_pdk = PDKVersion(pdk_name="nangate45")
        mismatch = PDKVersionMismatch(
            snapshot_pdk=snapshot_pdk,
            runtime_pdk=runtime_pdk,
        )

        warning = format_pdk_version_mismatch_warning(mismatch)

        # Should have separator lines for readability
        assert "=" * 80 in warning or "=" * 40 in warning


class TestEndToEndPDKMismatch:
    """End-to-end tests for PDK version mismatch workflow."""

    def test_step1_load_snapshot_with_pdk_version(self) -> None:
        """Step 1: Load snapshot created with PDK version X."""
        # Simulate snapshot metadata with PDK version
        snapshot_pdk = PDKVersion(
            pdk_name="nangate45",
            version="1.0",
            source="snapshot",
            metadata={"snapshot_path": "/path/to/snapshot"},
        )
        assert snapshot_pdk.pdk_name == "nangate45"
        assert snapshot_pdk.version == "1.0"

    def test_step2_attempt_execution_with_different_pdk_version(self) -> None:
        """Step 2: Attempt execution with PDK version Y."""
        # Simulate runtime environment with different PDK
        runtime_pdk = PDKVersion(
            pdk_name="nangate45",
            version="2.0",
            source="container",
            metadata={"container": "efabless/openlane:ci2504-dev-amd64"},
        )
        assert runtime_pdk.pdk_name == "nangate45"
        assert runtime_pdk.version == "2.0"

    def test_step3_detect_version_mismatch(self) -> None:
        """Step 3: Detect version mismatch."""
        snapshot_pdk = PDKVersion(pdk_name="nangate45", version="1.0", source="snapshot")
        runtime_pdk = PDKVersion(pdk_name="nangate45", version="2.0", source="container")

        mismatch = detect_pdk_version_mismatch(snapshot_pdk, runtime_pdk)

        assert mismatch is not None
        assert mismatch.snapshot_pdk.version == "1.0"
        assert mismatch.runtime_pdk.version == "2.0"

    def test_step4_classify_as_configuration_error(self) -> None:
        """Step 4: Classify as configuration error."""
        snapshot_pdk = PDKVersion(pdk_name="sky130", variant="sky130A")
        runtime_pdk = PDKVersion(pdk_name="sky130", variant="sky130B")

        mismatch = detect_pdk_version_mismatch(snapshot_pdk, runtime_pdk)

        # Mismatch should be classified as error severity
        assert mismatch is not None
        assert mismatch.severity == "error"
        # In integration, this would map to FailureType.CONFIGURATION_ERROR

    def test_step5_emit_clear_warning(self) -> None:
        """Step 5: Emit clear warning about version incompatibility."""
        snapshot_pdk = PDKVersion(pdk_name="asap7", version="r1p7")
        runtime_pdk = PDKVersion(pdk_name="asap7", version="r1p8")

        mismatch = detect_pdk_version_mismatch(snapshot_pdk, runtime_pdk)
        assert mismatch is not None

        warning = format_pdk_version_mismatch_warning(mismatch)

        # Warning should be clear and actionable
        assert "MISMATCH" in warning
        assert "asap7" in warning
        assert "r1p7" in warning
        assert "r1p8" in warning
        assert "RECOMMENDATION" in warning

    def test_compatible_pdks_no_warning(self) -> None:
        """Test no mismatch for compatible PDKs (happy path)."""
        snapshot_pdk = PDKVersion(pdk_name="nangate45", version="1.0")
        runtime_pdk = PDKVersion(pdk_name="nangate45", version="1.0")

        mismatch = detect_pdk_version_mismatch(snapshot_pdk, runtime_pdk)

        # No mismatch - trial can proceed normally
        assert mismatch is None

    def test_version_tracking_disabled_no_error(self) -> None:
        """Test graceful handling when version tracking is not enabled."""
        # If snapshot doesn't have PDK version, no error should occur
        mismatch = detect_pdk_version_mismatch(None, None)
        assert mismatch is None

        # If only one side has version info, also no error
        runtime_pdk = PDKVersion(pdk_name="nangate45", version="1.0")
        mismatch = detect_pdk_version_mismatch(None, runtime_pdk)
        assert mismatch is None
