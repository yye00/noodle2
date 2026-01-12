"""Tests for F273: Clone OpenROAD-flow-scripts (ORFS) and verify PDK/design availability.

Feature F273 Requirements:
1. Step 1: Clone https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git to ./orfs/
2. Step 2: Verify Nangate45 platform exists at orfs/flow/platforms/nangate45/
3. Step 3: Verify ASAP7 platform exists at orfs/flow/platforms/asap7/
4. Step 4: Verify Sky130 platform exists at orfs/flow/platforms/sky130hd/
5. Step 5: Verify GCD design exists for Nangate45
6. Step 6: Create script to verify ORFS installation
"""

from pathlib import Path

import pytest

from src.infrastructure import (
    check_orfs_cloned,
    get_available_designs,
    get_available_platforms,
    verify_design,
    verify_orfs_installation,
    verify_platform,
)


# Expected ORFS path
ORFS_PATH = Path("./orfs")


class TestStep1ORFSClone:
    """Test Step 1: Clone OpenROAD-flow-scripts to ./orfs/."""

    def test_orfs_directory_exists(self) -> None:
        """Verify that orfs/ directory exists."""
        assert ORFS_PATH.exists(), "ORFS directory not found"
        assert ORFS_PATH.is_dir(), "ORFS path is not a directory"

    def test_orfs_flow_directory_exists(self) -> None:
        """Verify that orfs/flow/ directory exists."""
        flow_path = ORFS_PATH / "flow"
        assert flow_path.exists(), "ORFS flow directory not found"
        assert flow_path.is_dir(), "ORFS flow path is not a directory"

    def test_orfs_platforms_directory_exists(self) -> None:
        """Verify that orfs/flow/platforms/ directory exists."""
        platforms_path = ORFS_PATH / "flow" / "platforms"
        assert platforms_path.exists(), "ORFS platforms directory not found"
        assert platforms_path.is_dir(), "ORFS platforms path is not a directory"

    def test_orfs_designs_directory_exists(self) -> None:
        """Verify that orfs/flow/designs/ directory exists."""
        designs_path = ORFS_PATH / "flow" / "designs"
        assert designs_path.exists(), "ORFS designs directory not found"
        assert designs_path.is_dir(), "ORFS designs path is not a directory"

    def test_check_orfs_cloned_function(self) -> None:
        """Test check_orfs_cloned function."""
        assert check_orfs_cloned(ORFS_PATH), "ORFS should be cloned"


class TestStep2Nangate45Platform:
    """Test Step 2: Verify Nangate45 platform exists."""

    def test_nangate45_platform_directory_exists(self) -> None:
        """Verify that Nangate45 platform directory exists."""
        nangate45_path = ORFS_PATH / "flow" / "platforms" / "nangate45"
        assert nangate45_path.exists(), "Nangate45 platform directory not found"
        assert nangate45_path.is_dir(), "Nangate45 platform is not a directory"

    def test_verify_nangate45_platform_function(self) -> None:
        """Test verify_platform function for Nangate45."""
        result = verify_platform("nangate45", ORFS_PATH)
        assert result.available, f"Nangate45 not available: {result.error}"
        assert result.platform_name == "nangate45"
        assert result.path is not None
        assert result.path.exists()


class TestStep3ASAP7Platform:
    """Test Step 3: Verify ASAP7 platform exists."""

    def test_asap7_platform_directory_exists(self) -> None:
        """Verify that ASAP7 platform directory exists."""
        asap7_path = ORFS_PATH / "flow" / "platforms" / "asap7"
        assert asap7_path.exists(), "ASAP7 platform directory not found"
        assert asap7_path.is_dir(), "ASAP7 platform is not a directory"

    def test_verify_asap7_platform_function(self) -> None:
        """Test verify_platform function for ASAP7."""
        result = verify_platform("asap7", ORFS_PATH)
        assert result.available, f"ASAP7 not available: {result.error}"
        assert result.platform_name == "asap7"
        assert result.path is not None
        assert result.path.exists()


class TestStep4Sky130Platform:
    """Test Step 4: Verify Sky130 platform exists."""

    def test_sky130hd_platform_directory_exists(self) -> None:
        """Verify that Sky130HD platform directory exists."""
        sky130_path = ORFS_PATH / "flow" / "platforms" / "sky130hd"
        assert sky130_path.exists(), "Sky130HD platform directory not found"
        assert sky130_path.is_dir(), "Sky130HD platform is not a directory"

    def test_verify_sky130hd_platform_function(self) -> None:
        """Test verify_platform function for Sky130HD."""
        result = verify_platform("sky130hd", ORFS_PATH)
        assert result.available, f"Sky130HD not available: {result.error}"
        assert result.platform_name == "sky130hd"
        assert result.path is not None
        assert result.path.exists()


class TestStep5GCDDesign:
    """Test Step 5: Verify GCD design exists for Nangate45."""

    def test_gcd_design_directory_exists(self) -> None:
        """Verify that GCD design directory exists for Nangate45."""
        gcd_path = ORFS_PATH / "flow" / "designs" / "nangate45" / "gcd"
        assert gcd_path.exists(), "GCD design directory not found"
        assert gcd_path.is_dir(), "GCD design is not a directory"

    def test_gcd_config_mk_exists(self) -> None:
        """Verify that GCD design has config.mk file."""
        config_path = ORFS_PATH / "flow" / "designs" / "nangate45" / "gcd" / "config.mk"
        assert config_path.exists(), "GCD config.mk not found"
        assert config_path.is_file(), "GCD config.mk is not a file"

    def test_verify_gcd_design_function(self) -> None:
        """Test verify_design function for GCD."""
        result = verify_design("gcd", "nangate45", ORFS_PATH)
        assert result.available, f"GCD design not available: {result.error}"
        assert result.design_name == "gcd"
        assert result.platform == "nangate45"
        assert result.path is not None
        assert result.path.exists()
        assert result.config_exists, "GCD config.mk should exist"


class TestStep6VerificationScript:
    """Test Step 6: Create script to verify ORFS installation."""

    def test_check_orfs_cloned_returns_true(self) -> None:
        """Test that check_orfs_cloned returns True for valid installation."""
        assert check_orfs_cloned(ORFS_PATH)

    def test_verify_platform_for_all_required_platforms(self) -> None:
        """Test verify_platform for all required platforms."""
        required_platforms = ["nangate45", "asap7", "sky130hd"]

        for platform in required_platforms:
            result = verify_platform(platform, ORFS_PATH)
            assert result.available, f"{platform} not available: {result.error}"
            assert result.path is not None

    def test_verify_design_for_nangate45_gcd(self) -> None:
        """Test verify_design for Nangate45 GCD."""
        result = verify_design("gcd", "nangate45", ORFS_PATH)
        assert result.available, f"GCD not available: {result.error}"
        assert result.config_exists

    def test_get_available_platforms_returns_list(self) -> None:
        """Test get_available_platforms function."""
        platforms = get_available_platforms(ORFS_PATH)
        assert isinstance(platforms, list)
        assert len(platforms) > 0
        assert "nangate45" in platforms
        assert "asap7" in platforms
        assert "sky130hd" in platforms

    def test_get_available_designs_for_nangate45(self) -> None:
        """Test get_available_designs for Nangate45."""
        designs = get_available_designs("nangate45", ORFS_PATH)
        assert isinstance(designs, list)
        assert len(designs) > 0
        assert "gcd" in designs

    def test_verify_orfs_installation_comprehensive(self) -> None:
        """Test verify_orfs_installation comprehensive check."""
        result = verify_orfs_installation(ORFS_PATH)
        assert result.orfs_cloned, "ORFS should be cloned"
        assert result.orfs_path == ORFS_PATH

        # Check required platforms
        assert result.platforms_available["nangate45"], "Nangate45 should be available"
        assert result.platforms_available["asap7"], "ASAP7 should be available"
        assert result.platforms_available["sky130hd"], "Sky130HD should be available"

        # Check required designs
        assert (
            result.designs_available["nangate45/gcd"]
        ), "Nangate45 GCD should be available"

        # Should have no errors
        assert len(result.errors) == 0, f"Unexpected errors: {result.errors}"
        assert result.all_checks_passed, "All checks should pass"


class TestVerificationEdgeCases:
    """Test edge cases and error handling."""

    def test_verify_nonexistent_platform(self) -> None:
        """Test verifying a platform that doesn't exist."""
        result = verify_platform("nonexistent_platform", ORFS_PATH)
        assert not result.available
        assert result.error is not None

    def test_verify_nonexistent_design(self) -> None:
        """Test verifying a design that doesn't exist."""
        result = verify_design("nonexistent_design", "nangate45", ORFS_PATH)
        assert not result.available
        assert result.error is not None

    def test_check_orfs_cloned_with_invalid_path(self) -> None:
        """Test check_orfs_cloned with invalid path."""
        invalid_path = Path("/nonexistent/path")
        assert not check_orfs_cloned(invalid_path)

    def test_get_available_platforms_with_invalid_path(self) -> None:
        """Test get_available_platforms with invalid path."""
        invalid_path = Path("/nonexistent/path")
        platforms = get_available_platforms(invalid_path)
        assert isinstance(platforms, list)
        assert len(platforms) == 0

    def test_get_available_designs_with_invalid_platform(self) -> None:
        """Test get_available_designs with invalid platform."""
        designs = get_available_designs("nonexistent_platform", ORFS_PATH)
        assert isinstance(designs, list)
        assert len(designs) == 0


class TestF273Integration:
    """Integration tests covering all F273 requirements."""

    def test_complete_f273_workflow(self) -> None:
        """Test complete F273 workflow: clone verification, platform checks, design checks."""
        # Step 1: Verify ORFS is cloned
        assert check_orfs_cloned(ORFS_PATH)

        # Step 2: Verify Nangate45 platform
        nangate45_result = verify_platform("nangate45", ORFS_PATH)
        assert nangate45_result.available

        # Step 3: Verify ASAP7 platform
        asap7_result = verify_platform("asap7", ORFS_PATH)
        assert asap7_result.available

        # Step 4: Verify Sky130HD platform
        sky130_result = verify_platform("sky130hd", ORFS_PATH)
        assert sky130_result.available

        # Step 5: Verify GCD design for Nangate45
        gcd_result = verify_design("gcd", "nangate45", ORFS_PATH)
        assert gcd_result.available
        assert gcd_result.config_exists

        # Step 6: Verify comprehensive installation check
        orfs_result = verify_orfs_installation(ORFS_PATH)
        assert orfs_result.all_checks_passed

    def test_f273_all_verification_steps_pass(self) -> None:
        """Verify all F273 steps pass in sequence."""
        # Perform comprehensive verification
        result = verify_orfs_installation(ORFS_PATH)

        # All checks should pass
        assert result.orfs_cloned, "ORFS should be cloned"
        assert result.platforms_available["nangate45"], "Nangate45 should be available"
        assert result.platforms_available["asap7"], "ASAP7 should be available"
        assert result.platforms_available["sky130hd"], "Sky130HD should be available"
        assert result.designs_available["nangate45/gcd"], "GCD design should be available"
        assert result.all_checks_passed, "All infrastructure checks should pass"
        assert len(result.errors) == 0, "No errors should be present"


class TestORFSVerificationFunctions:
    """Additional tests for ORFS verification functions."""

    def test_platform_verification_returns_valid_result(self) -> None:
        """Test that verify_platform returns valid result."""
        result = verify_platform("nangate45", ORFS_PATH)
        assert isinstance(result.available, bool)
        if result.available:
            assert result.path is not None
        else:
            assert result.error is not None

    def test_design_verification_returns_valid_result(self) -> None:
        """Test that verify_design returns valid result."""
        result = verify_design("gcd", "nangate45", ORFS_PATH)
        assert isinstance(result.available, bool)
        if result.available:
            assert result.path is not None
            assert isinstance(result.config_exists, bool)
        else:
            assert result.error is not None

    def test_orfs_verification_result_has_all_fields(self) -> None:
        """Test that ORFS verification result has all expected fields."""
        result = verify_orfs_installation(ORFS_PATH)
        assert hasattr(result, "orfs_cloned")
        assert hasattr(result, "orfs_path")
        assert hasattr(result, "platforms_available")
        assert hasattr(result, "designs_available")
        assert hasattr(result, "errors")
        assert hasattr(result, "all_checks_passed")

    def test_verification_result_errors_is_list(self) -> None:
        """Test that errors field is always a list."""
        result = verify_orfs_installation(ORFS_PATH)
        assert isinstance(result.errors, list)

    def test_platforms_available_is_dict(self) -> None:
        """Test that platforms_available is a dictionary."""
        result = verify_orfs_installation(ORFS_PATH)
        assert isinstance(result.platforms_available, dict)

    def test_designs_available_is_dict(self) -> None:
        """Test that designs_available is a dictionary."""
        result = verify_orfs_installation(ORFS_PATH)
        assert isinstance(result.designs_available, dict)


class TestAdditionalDesigns:
    """Test additional designs beyond GCD."""

    def test_ibex_design_exists_for_nangate45(self) -> None:
        """Test that ibex design exists for Nangate45."""
        result = verify_design("ibex", "nangate45", ORFS_PATH)
        # Just check if it exists, don't assert (might not be in all ORFS versions)
        if result.available:
            assert result.path is not None

    def test_multiple_designs_available_for_nangate45(self) -> None:
        """Test that multiple designs are available for Nangate45."""
        designs = get_available_designs("nangate45", ORFS_PATH)
        assert len(designs) >= 1  # At least GCD should be present
        assert "gcd" in designs
