"""Tests for F019 (CellResizeECO) and F020 (CellSwapECO).

Feature F019: CellResizeECO can be defined and generates valid TCL
Feature F020: CellSwapECO can be defined and generates valid TCL

Both features depend on F004 (StudyConfig can be loaded from YAML).
"""

import pytest

from src.controller.eco import (
    CellResizeECO,
    CellSwapECO,
    create_eco,
)
from src.controller.types import ECOClass


class TestF019CellResizeECO:
    """Tests for Feature F019: CellResizeECO definition and TCL generation."""

    def test_step_1_create_cell_resize_eco_instance(self) -> None:
        """
        Step 1: Create CellResizeECO instance.

        Verify that CellResizeECO can be instantiated with default parameters.
        """
        eco = CellResizeECO()

        assert eco is not None
        assert eco.name == "cell_resize"
        assert eco.eco_class == ECOClass.PLACEMENT_LOCAL
        assert eco.metadata.description == "Resize cells on critical paths to improve timing"

        print("✓ CellResizeECO instance created successfully")
        print(f"  Name: {eco.name}")
        print(f"  Class: {eco.eco_class}")
        print(f"  Description: {eco.metadata.description}")

    def test_step_2_set_size_multiplier_parameter(self) -> None:
        """
        Step 2: Set size_multiplier parameter.

        Verify that size_multiplier can be set during construction.
        """
        eco = CellResizeECO(size_multiplier=2.0)

        assert eco.metadata.parameters["size_multiplier"] == 2.0
        print("✓ size_multiplier parameter set to 2.0")

        # Test with different values
        eco2 = CellResizeECO(size_multiplier=1.5)
        assert eco2.metadata.parameters["size_multiplier"] == 1.5
        print("✓ size_multiplier parameter set to 1.5")

        # Test default value
        eco3 = CellResizeECO()
        assert eco3.metadata.parameters["size_multiplier"] == 1.5  # Default
        print(f"✓ Default size_multiplier: {eco3.metadata.parameters['size_multiplier']}")

    def test_step_3_set_max_paths_parameter(self) -> None:
        """
        Step 3: Set max_paths parameter.

        Verify that max_paths can be set during construction.
        """
        eco = CellResizeECO(max_paths=50)

        assert eco.metadata.parameters["max_paths"] == 50
        print("✓ max_paths parameter set to 50")

        # Test with different values
        eco2 = CellResizeECO(max_paths=200)
        assert eco2.metadata.parameters["max_paths"] == 200
        print("✓ max_paths parameter set to 200")

        # Test default value
        eco3 = CellResizeECO()
        assert eco3.metadata.parameters["max_paths"] == 100  # Default
        print(f"✓ Default max_paths: {eco3.metadata.parameters['max_paths']}")

    def test_step_4_call_generate_tcl_method(self) -> None:
        """
        Step 4: Call generate_tcl() method.

        Verify that generate_tcl() returns a valid TCL script string.
        """
        eco = CellResizeECO(size_multiplier=1.5, max_paths=100)

        tcl_script = eco.generate_tcl()

        assert tcl_script is not None
        assert isinstance(tcl_script, str)
        assert len(tcl_script) > 0
        print("✓ generate_tcl() returned a valid TCL script")
        print(f"  Script length: {len(tcl_script)} characters")
        print(f"  Script lines: {len(tcl_script.splitlines())} lines")

    def test_step_5_verify_tcl_contains_repair_design_or_resize_commands(self) -> None:
        """
        Step 5: Verify TCL contains repair_design or similar resize commands.

        The generated TCL should include OpenROAD commands for cell resizing.
        """
        eco = CellResizeECO(size_multiplier=2.0, max_paths=50)

        tcl_script = eco.generate_tcl()

        # Check for repair_design command (primary method)
        assert "repair_design" in tcl_script, "TCL should contain 'repair_design' command"
        print("✓ TCL contains 'repair_design' command")

        # Check for size multiplier in comments
        assert "2.0" in tcl_script or "2.0x" in tcl_script
        print("✓ TCL includes size_multiplier parameter")

        # Check for max_paths in script
        assert "50" in tcl_script
        print("✓ TCL includes max_paths parameter")

        # Check for cell resizing mention
        assert "resize" in tcl_script.lower() or "upsize" in tcl_script.lower()
        print("✓ TCL mentions cell resizing/upsizing")

        # Print sample of TCL for inspection
        print("\n--- Sample TCL Script ---")
        print(tcl_script[:400])
        print("...")

    def test_validate_parameters(self) -> None:
        """Test parameter validation for CellResizeECO."""
        # Valid parameters
        eco = CellResizeECO(size_multiplier=1.5, max_paths=100)
        assert eco.validate_parameters() is True
        print("✓ Valid parameters accepted")

        # Invalid size_multiplier (< 1.0)
        eco_invalid = CellResizeECO(size_multiplier=0.5, max_paths=100)
        assert eco_invalid.validate_parameters() is False
        print("✓ Invalid size_multiplier (<1.0) rejected")

        # Invalid max_paths (< 1)
        eco_invalid2 = CellResizeECO(size_multiplier=1.5, max_paths=0)
        assert eco_invalid2.validate_parameters() is False
        print("✓ Invalid max_paths (<1) rejected")

    def test_eco_metadata(self) -> None:
        """Test CellResizeECO metadata."""
        eco = CellResizeECO()

        # Check metadata fields
        assert eco.metadata.name == "cell_resize"
        assert eco.metadata.eco_class == ECOClass.PLACEMENT_LOCAL
        assert eco.metadata.version == "1.0"
        assert "timing_optimization" in eco.metadata.tags
        assert "cell_sizing" in eco.metadata.tags

        print("✓ CellResizeECO metadata is correct")
        print(f"  Tags: {eco.metadata.tags}")

    def test_create_via_factory(self) -> None:
        """Test creating CellResizeECO via factory function."""
        eco = create_eco("cell_resize", size_multiplier=2.0, max_paths=75)

        assert isinstance(eco, CellResizeECO)
        assert eco.metadata.parameters["size_multiplier"] == 2.0
        assert eco.metadata.parameters["max_paths"] == 75

        print("✓ CellResizeECO created successfully via factory")

    def test_to_dict_serialization(self) -> None:
        """Test CellResizeECO serialization."""
        eco = CellResizeECO(size_multiplier=1.8, max_paths=120)

        eco_dict = eco.to_dict()

        assert eco_dict["name"] == "cell_resize"
        assert eco_dict["eco_class"] == "placement_local"
        assert eco_dict["parameters"]["size_multiplier"] == 1.8
        assert eco_dict["parameters"]["max_paths"] == 120

        print("✓ CellResizeECO serializes correctly to dict")


class TestF020CellSwapECO:
    """Tests for Feature F020: CellSwapECO definition and TCL generation."""

    def test_step_1_create_cell_swap_eco_instance(self) -> None:
        """
        Step 1: Create CellSwapECO instance.

        Verify that CellSwapECO can be instantiated with default parameters.
        """
        eco = CellSwapECO()

        assert eco is not None
        assert eco.name == "cell_swap"
        assert eco.eco_class == ECOClass.PLACEMENT_LOCAL
        assert eco.metadata.description == "Swap cells to faster variants on critical paths"

        print("✓ CellSwapECO instance created successfully")
        print(f"  Name: {eco.name}")
        print(f"  Class: {eco.eco_class}")
        print(f"  Description: {eco.metadata.description}")

    def test_step_2_set_path_count_parameter(self) -> None:
        """
        Step 2: Set path_count parameter.

        Verify that path_count can be set during construction.
        """
        eco = CellSwapECO(path_count=100)

        assert eco.metadata.parameters["path_count"] == 100
        print("✓ path_count parameter set to 100")

        # Test with different values
        eco2 = CellSwapECO(path_count=200)
        assert eco2.metadata.parameters["path_count"] == 200
        print("✓ path_count parameter set to 200")

        # Test default value
        eco3 = CellSwapECO()
        assert eco3.metadata.parameters["path_count"] == 50  # Default
        print(f"✓ Default path_count: {eco3.metadata.parameters['path_count']}")

    def test_step_3_call_generate_tcl_method(self) -> None:
        """
        Step 3: Call generate_tcl() method.

        Verify that generate_tcl() returns a valid TCL script string.
        """
        eco = CellSwapECO(path_count=75)

        tcl_script = eco.generate_tcl()

        assert tcl_script is not None
        assert isinstance(tcl_script, str)
        assert len(tcl_script) > 0
        print("✓ generate_tcl() returned a valid TCL script")
        print(f"  Script length: {len(tcl_script)} characters")
        print(f"  Script lines: {len(tcl_script.splitlines())} lines")

    def test_step_4_verify_tcl_contains_cell_swap_commands(self) -> None:
        """
        Step 4: Verify TCL contains commands to swap cells to faster variants.

        The generated TCL should include OpenROAD commands for cell swapping.
        """
        eco = CellSwapECO(path_count=60)

        tcl_script = eco.generate_tcl()

        # Check for repair_timing command (used for VT swapping and upsizing)
        assert "repair_timing" in tcl_script, "TCL should contain 'repair_timing' command"
        print("✓ TCL contains 'repair_timing' command")

        # Check for path_count in script
        assert "60" in tcl_script
        print("✓ TCL includes path_count parameter")

        # Check for cell swapping mention
        assert "swap" in tcl_script.lower()
        print("✓ TCL mentions cell swapping")

        # Check for faster variants mention (HVT/RVT/LVT or drive strength)
        tcl_lower = tcl_script.lower()
        has_vt_swap = any(vt in tcl_lower for vt in ["hvt", "rvt", "lvt", "vt"])
        has_drive_swap = any(term in tcl_lower for term in ["drive", "strength", "x1", "x2"])

        assert has_vt_swap or has_drive_swap, "TCL should mention VT swapping or drive strength"
        print("✓ TCL mentions faster variants (VT or drive strength)")

        # Print sample of TCL for inspection
        print("\n--- Sample TCL Script ---")
        print(tcl_script[:400])
        print("...")

    def test_validate_parameters(self) -> None:
        """Test parameter validation for CellSwapECO."""
        # Valid parameters
        eco = CellSwapECO(path_count=50)
        assert eco.validate_parameters() is True
        print("✓ Valid parameters accepted")

        # Invalid path_count (< 1)
        eco_invalid = CellSwapECO(path_count=0)
        assert eco_invalid.validate_parameters() is False
        print("✓ Invalid path_count (<1) rejected")

        eco_invalid2 = CellSwapECO(path_count=-10)
        assert eco_invalid2.validate_parameters() is False
        print("✓ Invalid path_count (negative) rejected")

    def test_eco_metadata(self) -> None:
        """Test CellSwapECO metadata."""
        eco = CellSwapECO()

        # Check metadata fields
        assert eco.metadata.name == "cell_swap"
        assert eco.metadata.eco_class == ECOClass.PLACEMENT_LOCAL
        assert eco.metadata.version == "1.0"
        assert "timing_optimization" in eco.metadata.tags
        assert "cell_swapping" in eco.metadata.tags
        assert "vth_swapping" in eco.metadata.tags

        print("✓ CellSwapECO metadata is correct")
        print(f"  Tags: {eco.metadata.tags}")

    def test_create_via_factory(self) -> None:
        """Test creating CellSwapECO via factory function."""
        eco = create_eco("cell_swap", path_count=80)

        assert isinstance(eco, CellSwapECO)
        assert eco.metadata.parameters["path_count"] == 80

        print("✓ CellSwapECO created successfully via factory")

    def test_to_dict_serialization(self) -> None:
        """Test CellSwapECO serialization."""
        eco = CellSwapECO(path_count=90)

        eco_dict = eco.to_dict()

        assert eco_dict["name"] == "cell_swap"
        assert eco_dict["eco_class"] == "placement_local"
        assert eco_dict["parameters"]["path_count"] == 90

        print("✓ CellSwapECO serializes correctly to dict")


class TestF019F020Integration:
    """Integration tests for F019 and F020."""

    def test_both_ecos_have_consistent_api(self) -> None:
        """Test that both ECOs follow the same API pattern."""
        resize_eco = CellResizeECO()
        swap_eco = CellSwapECO()

        # Both should have generate_tcl method
        assert callable(resize_eco.generate_tcl)
        assert callable(swap_eco.generate_tcl)

        # Both should have validate_parameters method
        assert callable(resize_eco.validate_parameters)
        assert callable(swap_eco.validate_parameters)

        # Both should be PLACEMENT_LOCAL class
        assert resize_eco.eco_class == ECOClass.PLACEMENT_LOCAL
        assert swap_eco.eco_class == ECOClass.PLACEMENT_LOCAL

        print("✓ Both ECOs have consistent API")

    def test_both_ecos_are_in_registry(self) -> None:
        """Test that both ECOs are registered in the factory."""
        # Should be able to create via factory
        resize = create_eco("cell_resize")
        swap = create_eco("cell_swap")

        assert isinstance(resize, CellResizeECO)
        assert isinstance(swap, CellSwapECO)

        print("✓ Both ECOs are registered in factory")

    def test_both_ecos_generate_valid_tcl(self) -> None:
        """Test that both ECOs generate valid TCL scripts."""
        resize_eco = CellResizeECO(size_multiplier=1.5, max_paths=100)
        swap_eco = CellSwapECO(path_count=50)

        resize_tcl = resize_eco.generate_tcl()
        swap_tcl = swap_eco.generate_tcl()

        # Both should be non-empty strings
        assert isinstance(resize_tcl, str) and len(resize_tcl) > 0
        assert isinstance(swap_tcl, str) and len(swap_tcl) > 0

        # Both should contain OpenROAD commands
        assert "repair_design" in resize_tcl or "repair_timing" in resize_tcl
        assert "repair_timing" in swap_tcl or "repair_design" in swap_tcl

        print("✓ Both ECOs generate valid TCL scripts")

    def test_eco_names_are_unique(self) -> None:
        """Test that ECO names are unique."""
        resize = CellResizeECO()
        swap = CellSwapECO()

        assert resize.name != swap.name
        assert resize.name == "cell_resize"
        assert swap.name == "cell_swap"

        print("✓ ECO names are unique")
        print(f"  CellResizeECO: {resize.name}")
        print(f"  CellSwapECO: {swap.name}")

    def test_both_ecos_serialize_consistently(self) -> None:
        """Test that both ECOs serialize to dict consistently."""
        resize = CellResizeECO()
        swap = CellSwapECO()

        resize_dict = resize.to_dict()
        swap_dict = swap.to_dict()

        # Both should have the same top-level keys
        assert set(resize_dict.keys()) == set(swap_dict.keys())

        # Both should have required fields
        for eco_dict in [resize_dict, swap_dict]:
            assert "name" in eco_dict
            assert "eco_class" in eco_dict
            assert "description" in eco_dict
            assert "parameters" in eco_dict
            assert "version" in eco_dict
            assert "tags" in eco_dict

        print("✓ Both ECOs serialize consistently")
