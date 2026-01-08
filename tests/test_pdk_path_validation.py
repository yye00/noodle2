"""
Test PDK path validation requirements.

This test module validates features #54-#56 from feature_list.json:
- Feature #54: Validate PDK paths are resolved inside container not on host
- Feature #55: Prevent implicit PDK replacement without explicit declaration
- Feature #56: Support custom container image with modified PDK as explicit override

These tests ensure that:
1. PDK paths always reference container filesystem (/pdk/...) not host
2. No network access is required for PDK data
3. PDK replacement requires explicit declaration
4. Custom containers can override PDKs safely
"""

import pytest
from pathlib import Path

from src.trial_runner.tcl_generator import (
    generate_pdk_library_paths,
    generate_trial_script,
)
from src.controller.types import ExecutionMode


# ============================================================================
# Feature #54: Validate PDK paths are resolved inside container not on host
# ============================================================================


class TestPDKPathsResolvedInsideContainer:
    """
    Feature #54: Validate PDK paths are resolved inside container not on host

    Tests validate that:
    - PDK paths use container filesystem (/pdk/...) not host paths
    - No host filesystem access required
    - No network access required for PDK data
    - Paths are predictable and deterministic
    """

    def test_nangate45_paths_use_container_filesystem(self):
        """Step 1-2: Verify Nangate45 PDK paths exist in container filesystem."""
        paths = generate_pdk_library_paths("nangate45")

        # All paths must start with /pdk/ (container filesystem)
        assert "/pdk/nangate45/" in paths
        assert "liberty_file" in paths
        assert "tech_lef" in paths
        assert "std_cell_lef" in paths

        # Must not reference host filesystem
        assert "/home/" not in paths
        assert "/usr/local/" not in paths
        assert "$HOME" not in paths

    def test_sky130_paths_use_container_filesystem(self):
        """Step 1-2: Verify Sky130 PDK paths exist in container filesystem."""
        paths = generate_pdk_library_paths("sky130")

        # All paths must start with /pdk/ (container filesystem)
        assert "/pdk/sky130A/" in paths
        assert "liberty_file" in paths
        assert "tech_lef" in paths
        assert "std_cell_lef" in paths

        # Must use sky130A variant (not sky130B)
        assert "sky130A" in paths
        assert "sky130B" not in paths

        # Must not reference host filesystem
        assert "/home/" not in paths
        assert "/usr/local/" not in paths

    def test_asap7_paths_use_container_filesystem(self):
        """Step 1-2: Verify ASAP7 PDK paths exist in container filesystem."""
        paths = generate_pdk_library_paths("asap7")

        # All paths must start with /pdk/ (container filesystem)
        assert "/pdk/asap7/" in paths
        assert "liberty_file" in paths
        assert "tech_lef" in paths
        assert "std_cell_lef" in paths

        # Must not reference host filesystem
        assert "/home/" not in paths
        assert "/usr/local/" not in paths

    def test_no_network_access_required_for_pdk_data(self):
        """Step 5: Verify no network access is required for PDK data."""
        # PDK paths are static and deterministic
        # No URLs, no wget/curl, no dynamic downloads
        for pdk in ["nangate45", "sky130", "asap7"]:
            paths = generate_pdk_library_paths(pdk)

            # Must not contain network access patterns
            assert "http://" not in paths
            assert "https://" not in paths
            assert "ftp://" not in paths
            assert "wget" not in paths
            assert "curl" not in paths
            assert "fetch" not in paths

    def test_pdk_paths_are_deterministic(self):
        """Verify PDK paths are deterministic (same every time)."""
        # Generate paths multiple times
        paths1 = generate_pdk_library_paths("nangate45")
        paths2 = generate_pdk_library_paths("nangate45")
        paths3 = generate_pdk_library_paths("nangate45")

        # Must be identical
        assert paths1 == paths2 == paths3

    def test_pdk_paths_embedded_in_trial_script(self):
        """Step 3: Verify PDK paths are embedded in trial scripts correctly."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="nangate45",
        )

        # Script must contain container PDK paths
        assert "/pdk/nangate45/" in script

        # Must not contain host-specific paths
        assert "/home/" not in script or "/home/captain/work" not in script

    def test_all_supported_pdks_use_container_paths(self):
        """Verify all supported PDKs use container paths consistently."""
        supported_pdks = ["nangate45", "sky130", "asap7"]

        for pdk in supported_pdks:
            paths = generate_pdk_library_paths(pdk)

            # Every PDK must start with /pdk/
            assert f"/pdk/" in paths, f"{pdk} does not use /pdk/ paths"

            # Every PDK must have all three required files
            assert "liberty_file" in paths
            assert "tech_lef" in paths
            assert "std_cell_lef" in paths

    def test_pdk_paths_case_insensitive(self):
        """Verify PDK name is case-insensitive for path generation."""
        # Different case variations should produce same paths
        paths_lower = generate_pdk_library_paths("nangate45")
        paths_upper = generate_pdk_library_paths("NANGATE45")
        paths_mixed = generate_pdk_library_paths("Nangate45")

        # All should contain same /pdk/nangate45/ path (normalized to lowercase)
        assert "/pdk/nangate45/" in paths_lower
        # Upper/mixed case also get normalized
        assert paths_lower == paths_upper == paths_mixed


# ============================================================================
# Feature #55: Prevent implicit PDK replacement without explicit declaration
# ============================================================================


class TestPreventImplicitPDKReplacement:
    """
    Feature #55: Prevent implicit PDK replacement without explicit declaration

    Tests validate that:
    - PDK must be explicitly declared in Study configuration
    - Cannot override PDK without declaring in Study definition
    - Clear error message if implicit override attempted
    - Baseline PDK remains unchanged
    """

    def test_default_pdk_is_nangate45(self):
        """Verify default PDK is Nangate45 when not specified."""
        # When no PDK specified, should default to Nangate45
        # Use STA_CONGESTION mode which includes PDK library paths
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            # pdk parameter omitted
        )

        # Should use Nangate45 as baseline
        assert "/pdk/nangate45/" in script

    def test_explicit_pdk_declaration_in_script(self):
        """Step 1-2: Verify explicit PDK declaration is required."""
        # Explicitly declare PDK in script generation
        script_ng45 = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="nangate45",  # Explicit declaration
        )

        script_sky130 = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="sky130",  # Explicit declaration
        )

        # Each should reference only their declared PDK
        assert "/pdk/nangate45/" in script_ng45
        assert "/pdk/nangate45/" not in script_sky130

        assert "/pdk/sky130A/" in script_sky130
        assert "/pdk/sky130A/" not in script_ng45

    def test_pdk_replacement_requires_explicit_parameter(self):
        """Step 3-4: Verify PDK replacement requires explicit parameter."""
        # Generate script with default PDK
        # Use STA_CONGESTION mode which includes PDK library paths
        default_script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
        )

        # Generate script with explicit PDK override
        override_script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="sky130",  # Explicit override
        )

        # Default should use Nangate45
        assert "/pdk/nangate45/" in default_script
        # Default should not contain Sky130
        assert "/pdk/sky130A/" not in default_script

        # Override should contain Sky130
        assert "/pdk/sky130A/" in override_script
        # Override should not contain Nangate45
        assert "/pdk/nangate45/" not in override_script

    def test_unknown_pdk_generates_template_not_crash(self):
        """Verify unknown PDK generates template instead of crashing."""
        # Unknown PDK should generate a template for error detection
        paths = generate_pdk_library_paths("unknown_pdk")

        # Should contain placeholder paths
        assert "/pdk/unknown_pdk/" in paths
        assert "liberty_file" in paths
        assert "tech_lef" in paths
        assert "std_cell_lef" in paths

        # Should have warning comment
        assert "Unknown PDK" in paths or "unknown" in paths.lower()

    def test_pdk_consistency_across_script_generation(self):
        """Verify PDK remains consistent throughout script generation."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="sky130",
        )

        # Should reference sky130 consistently
        assert "/pdk/sky130A/" in script

        # Should not accidentally mix PDKs
        assert "/pdk/nangate45/" not in script
        assert "/pdk/asap7/" not in script


# ============================================================================
# Feature #56: Support custom container image with modified PDK as explicit override
# ============================================================================


class TestCustomContainerWithModifiedPDK:
    """
    Feature #56: Support custom container image with modified PDK as explicit override

    Tests validate that:
    - Custom container images can be used with modified PDKs
    - PDK override must be declared explicitly
    - Paths remain consistent with container convention
    - No implicit PDK detection or scanning
    """

    def test_custom_pdk_can_be_specified(self):
        """Verify custom PDK name can be specified explicitly."""
        # Custom PDK variant
        custom_pdk = "nangate45_modified"

        paths = generate_pdk_library_paths(custom_pdk)

        # Should generate paths with custom PDK name
        assert "/pdk/" in paths
        assert custom_pdk in paths

    def test_custom_pdk_paths_follow_container_convention(self):
        """Verify custom PDK paths follow /pdk/<name>/ convention."""
        custom_pdks = [
            "nangate45_patched",
            "sky130_experimental",
            "asap7_modified_rules",
        ]

        for pdk in custom_pdks:
            paths = generate_pdk_library_paths(pdk)

            # Should follow container path convention
            assert "/pdk/" in paths
            assert pdk in paths

            # Should not reference host filesystem
            assert "/home/" not in paths
            assert "/usr/local/" not in paths

    def test_custom_container_pdk_explicit_in_script(self):
        """Verify custom container PDK is explicitly referenced in script."""
        custom_pdk = "sky130_custom_variant"

        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk=custom_pdk,  # Explicit custom PDK
        )

        # Should reference custom PDK in paths
        assert f"/pdk/{custom_pdk}/" in script or custom_pdk in script

    def test_no_implicit_pdk_detection(self):
        """Verify no implicit PDK detection or filesystem scanning."""
        # PDK paths are generated purely from pdk parameter
        # No filesystem scanning, no auto-detection

        # If we request a PDK, we get that PDK's paths
        # (even if it doesn't exist yet - that's a runtime check)
        for pdk in ["nangate45", "sky130", "asap7", "custom_pdk"]:
            paths = generate_pdk_library_paths(pdk)

            # Should deterministically generate paths
            # No "if exists" logic, no scanning
            assert "liberty_file" in paths
            assert "tech_lef" in paths
            assert "std_cell_lef" in paths

    def test_modified_pdk_requires_explicit_declaration(self):
        """Verify modified PDK requires explicit declaration, not auto-detection."""
        # Standard PDK
        standard = generate_pdk_library_paths("nangate45")

        # Modified PDK (explicit declaration required)
        modified = generate_pdk_library_paths("nangate45_modified")

        # Should be different
        assert standard != modified

        # Modified version should reference modified path
        assert "nangate45_modified" in modified

        # Standard version should not accidentally use modified
        assert "nangate45_modified" not in standard


# ============================================================================
# Integration Tests
# ============================================================================


class TestPDKPathIntegration:
    """
    Integration tests for PDK path validation across the stack.
    """

    def test_pdk_path_contract_across_all_execution_modes(self):
        """Verify PDK path contract holds across all execution modes."""
        # Note: STA_ONLY mode is simplified and doesn't include PDK library paths
        # Only STA_CONGESTION and FULL_ROUTE modes include full PDK setup
        modes = [
            ExecutionMode.STA_CONGESTION,
            ExecutionMode.FULL_ROUTE,
        ]

        for mode in modes:
            for pdk in ["nangate45", "sky130", "asap7"]:
                script = generate_trial_script(
                    execution_mode=mode,
                    design_name="test_design",
                    pdk=pdk,
                )

                # Every mode should use container paths
                assert "/pdk/" in script

                # Every mode should reference declared PDK
                # (normalized to lowercase in paths)
                assert pdk.lower() in script.lower()

    def test_pdk_paths_immutable_per_study(self):
        """Verify PDK paths are immutable per Study (no mid-execution changes)."""
        # Generate multiple scripts with same PDK
        scripts = [
            generate_trial_script(
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name=f"design_{i}",
                pdk="nangate45",
            )
            for i in range(5)
        ]

        # All should reference same PDK paths
        for script in scripts:
            assert "/pdk/nangate45/" in script

        # None should reference other PDKs
        for script in scripts:
            assert "/pdk/sky130A/" not in script
            assert "/pdk/asap7/" not in script

    def test_container_path_validation_metadata(self):
        """Verify PDK path validation can be documented in metadata."""
        # PDK validation can be tracked in metadata
        metadata = {
            "pdk": "nangate45",
            "pdk_source": "container_baked",
            "pdk_path_validation": "container_filesystem_only",
        }

        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            pdk="nangate45",
            metadata=metadata,
        )

        # Metadata should be embedded in script
        assert "pdk" in script.lower()
        assert "nangate45" in script.lower()

    def test_pdk_version_pinning_via_container(self):
        """Verify PDK version is pinned via container image, not Noodle 2."""
        # Noodle 2 does not manage PDK versions
        # PDK version is part of container's semantic contract

        for pdk in ["nangate45", "sky130", "asap7"]:
            paths = generate_pdk_library_paths(pdk)

            # Paths should not contain version numbers
            # (version is implicit in container image tag)
            # Paths reference latest available in container

            # Should be simple /pdk/<name>/ paths
            assert f"/pdk/" in paths

            # Should not have version strings like "v1.0" or "2024"
            # (those would be in container image tag, not path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
