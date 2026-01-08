"""Tests for PDK validation functionality."""

import tempfile
from pathlib import Path

import pytest

from src.pdk import (
    PDKValidationError,
    PDKValidationResult,
    parse_lef_sites,
    parse_tech_lef_layers,
    validate_asap7_identifiers,
    validate_pdk_files,
)


class TestParseLEFSites:
    """Tests for parse_lef_sites function."""

    def test_parse_lef_with_single_site(self, tmp_path):
        """Step 2: Parse LEF to extract site names - single site."""
        lef_content = """
VERSION 5.8 ;
BUSBITCHARS "[]" ;

SITE asap7sc7p5t_28_R_24_NP_162NW_34O
  CLASS CORE ;
  SYMMETRY Y ;
  SIZE 0.054 BY 0.270 ;
END asap7sc7p5t_28_R_24_NP_162NW_34O
"""
        lef_file = tmp_path / "test.lef"
        lef_file.write_text(lef_content)

        sites = parse_lef_sites(lef_file)

        assert len(sites) == 1
        assert "asap7sc7p5t_28_R_24_NP_162NW_34O" in sites

    def test_parse_lef_with_multiple_sites(self, tmp_path):
        """Parse LEF with multiple SITE definitions."""
        lef_content = """
VERSION 5.8 ;

SITE site1
  CLASS CORE ;
END site1

SITE site2
  CLASS PAD ;
END site2

SITE asap7sc7p5t_28_R_24_NP_162NW_34O
  CLASS CORE ;
END asap7sc7p5t_28_R_24_NP_162NW_34O
"""
        lef_file = tmp_path / "test.lef"
        lef_file.write_text(lef_content)

        sites = parse_lef_sites(lef_file)

        assert len(sites) == 3
        assert "site1" in sites
        assert "site2" in sites
        assert "asap7sc7p5t_28_R_24_NP_162NW_34O" in sites

    def test_parse_lef_with_no_sites(self, tmp_path):
        """Parse LEF with no SITE definitions."""
        lef_content = """
VERSION 5.8 ;
BUSBITCHARS "[]" ;
"""
        lef_file = tmp_path / "test.lef"
        lef_file.write_text(lef_content)

        sites = parse_lef_sites(lef_file)

        assert len(sites) == 0

    def test_parse_lef_file_not_found(self):
        """Parse LEF raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="LEF file not found"):
            parse_lef_sites("/nonexistent/file.lef")


class TestParseTechLEFLayers:
    """Tests for parse_tech_lef_layers function."""

    def test_parse_tech_lef_with_metal_layers(self, tmp_path):
        """Step 4: Parse tech file to extract metal layer names."""
        tech_lef_content = """
VERSION 5.8 ;

LAYER metal1
  TYPE ROUTING ;
END metal1

LAYER metal2
  TYPE ROUTING ;
END metal2

LAYER metal3
  TYPE ROUTING ;
END metal3

LAYER metal9
  TYPE ROUTING ;
END metal9
"""
        tech_lef_file = tmp_path / "tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        layers = parse_tech_lef_layers(tech_lef_file)

        assert len(layers) == 4
        assert "metal1" in layers
        assert "metal2" in layers
        assert "metal3" in layers
        assert "metal9" in layers

    def test_parse_tech_lef_layers_sorted(self, tmp_path):
        """Parse tech LEF returns layers in numerical order."""
        tech_lef_content = """
LAYER metal9
  TYPE ROUTING ;
END metal9

LAYER metal2
  TYPE ROUTING ;
END metal2

LAYER metal5
  TYPE ROUTING ;
END metal5
"""
        tech_lef_file = tmp_path / "tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        layers = parse_tech_lef_layers(tech_lef_file)

        # Should be sorted numerically
        assert layers == ["metal2", "metal5", "metal9"]

    def test_parse_tech_lef_case_insensitive(self, tmp_path):
        """Parse tech LEF handles mixed case METAL/metal."""
        tech_lef_content = """
LAYER METAL2
  TYPE ROUTING ;
END METAL2

LAYER Metal3
  TYPE ROUTING ;
END Metal3

LAYER metal4
  TYPE ROUTING ;
END metal4
"""
        tech_lef_file = tmp_path / "tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        layers = parse_tech_lef_layers(tech_lef_file)

        # All should be normalized to lowercase
        assert layers == ["metal2", "metal3", "metal4"]

    def test_parse_tech_lef_ignores_non_metal_layers(self, tmp_path):
        """Parse tech LEF ignores non-metal layers (via, poly, etc)."""
        tech_lef_content = """
LAYER poly
  TYPE MASTERSLICE ;
END poly

LAYER metal2
  TYPE ROUTING ;
END metal2

LAYER via1
  TYPE CUT ;
END via1

LAYER metal3
  TYPE ROUTING ;
END metal3
"""
        tech_lef_file = tmp_path / "tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        layers = parse_tech_lef_layers(tech_lef_file)

        # Should only extract metal layers
        assert layers == ["metal2", "metal3"]

    def test_parse_tech_lef_file_not_found(self):
        """Parse tech LEF raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="Tech LEF file not found"):
            parse_tech_lef_layers("/nonexistent/tech.lef")

    def test_parse_tech_lef_with_no_metal_layers(self, tmp_path):
        """Parse tech LEF with no metal layers returns empty list."""
        tech_lef_content = """
VERSION 5.8 ;

LAYER poly
  TYPE MASTERSLICE ;
END poly
"""
        tech_lef_file = tmp_path / "tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        layers = parse_tech_lef_layers(tech_lef_file)

        assert len(layers) == 0


class TestValidateASAP7Identifiers:
    """Tests for validate_asap7_identifiers function."""

    def test_validate_asap7_with_correct_identifiers(self, tmp_path):
        """Step 3: Verify site name and Step 5: Verify metal layers match expected naming."""
        # Create LEF with correct ASAP7 site
        lef_content = """
SITE asap7sc7p5t_28_R_24_NP_162NW_34O
  CLASS CORE ;
END asap7sc7p5t_28_R_24_NP_162NW_34O
"""
        lef_file = tmp_path / "asap7.lef"
        lef_file.write_text(lef_content)

        # Create tech LEF with correct metal layers
        tech_lef_content = """
LAYER metal2
  TYPE ROUTING ;
END metal2

LAYER metal3
  TYPE ROUTING ;
END metal3

LAYER metal4
  TYPE ROUTING ;
END metal4

LAYER metal5
  TYPE ROUTING ;
END metal5

LAYER metal6
  TYPE ROUTING ;
END metal6

LAYER metal7
  TYPE ROUTING ;
END metal7

LAYER metal8
  TYPE ROUTING ;
END metal8

LAYER metal9
  TYPE ROUTING ;
END metal9
"""
        tech_lef_file = tmp_path / "asap7_tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        result = validate_asap7_identifiers(lef_file, tech_lef_file)

        assert result.is_valid is True
        assert result.pdk_name == "asap7"
        assert len(result.errors) == 0
        assert "parse_lef_sites" in result.checks_performed
        assert "parse_tech_lef_layers" in result.checks_performed
        assert result.metadata["site_validated"] == "asap7sc7p5t_28_R_24_NP_162NW_34O"
        assert "metal2" in result.metadata["metal_layers_validated"]
        assert "metal9" in result.metadata["metal_layers_validated"]

    def test_validate_asap7_with_wrong_site_name(self, tmp_path):
        """Step 6: Fail fast with configuration error if identifiers mismatch."""
        # Create LEF with wrong site name
        lef_content = """
SITE wrong_site_name
  CLASS CORE ;
END wrong_site_name
"""
        lef_file = tmp_path / "asap7.lef"
        lef_file.write_text(lef_content)

        # Create tech LEF with correct metal layers
        tech_lef_content = """
LAYER metal2
  TYPE ROUTING ;
END metal2

LAYER metal9
  TYPE ROUTING ;
END metal9
"""
        tech_lef_file = tmp_path / "asap7_tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        result = validate_asap7_identifiers(lef_file, tech_lef_file)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("asap7sc7p5t_28_R_24_NP_162NW_34O" in error for error in result.errors)
        assert any("not found" in error for error in result.errors)

    def test_validate_asap7_with_missing_metal_layers(self, tmp_path):
        """Validate ASAP7 fails if required metal layers are missing."""
        # Create LEF with correct site
        lef_content = """
SITE asap7sc7p5t_28_R_24_NP_162NW_34O
  CLASS CORE ;
END asap7sc7p5t_28_R_24_NP_162NW_34O
"""
        lef_file = tmp_path / "asap7.lef"
        lef_file.write_text(lef_content)

        # Create tech LEF with only metal2 and metal3 (missing metal4-metal9)
        tech_lef_content = """
LAYER metal2
  TYPE ROUTING ;
END metal2

LAYER metal3
  TYPE ROUTING ;
END metal3
"""
        tech_lef_file = tmp_path / "asap7_tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        result = validate_asap7_identifiers(lef_file, tech_lef_file)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("missing" in error.lower() for error in result.errors)
        assert any("metal4" in error for error in result.errors)

    def test_validate_asap7_with_extra_metal_layers(self, tmp_path):
        """Validate ASAP7 with extra metal layers shows warning but passes."""
        # Create LEF with correct site
        lef_content = """
SITE asap7sc7p5t_28_R_24_NP_162NW_34O
  CLASS CORE ;
END asap7sc7p5t_28_R_24_NP_162NW_34O
"""
        lef_file = tmp_path / "asap7.lef"
        lef_file.write_text(lef_content)

        # Create tech LEF with expected layers plus metal10
        tech_lef_content = """
LAYER metal2
  TYPE ROUTING ;
END metal2

LAYER metal3
  TYPE ROUTING ;
END metal3

LAYER metal4
  TYPE ROUTING ;
END metal4

LAYER metal5
  TYPE ROUTING ;
END metal5

LAYER metal6
  TYPE ROUTING ;
END metal6

LAYER metal7
  TYPE ROUTING ;
END metal7

LAYER metal8
  TYPE ROUTING ;
END metal8

LAYER metal9
  TYPE ROUTING ;
END metal9

LAYER metal10
  TYPE ROUTING ;
END metal10
"""
        tech_lef_file = tmp_path / "asap7_tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        result = validate_asap7_identifiers(lef_file, tech_lef_file)

        # Should pass but with warning about extra layer
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("metal10" in warning for warning in result.warnings)

    def test_validate_asap7_result_to_dict(self, tmp_path):
        """Validate ASAP7 result can be serialized to dict."""
        lef_content = """
SITE asap7sc7p5t_28_R_24_NP_162NW_34O
  CLASS CORE ;
END asap7sc7p5t_28_R_24_NP_162NW_34O
"""
        lef_file = tmp_path / "asap7.lef"
        lef_file.write_text(lef_content)

        tech_lef_content = """
LAYER metal2
  TYPE ROUTING ;
END metal2
"""
        tech_lef_file = tmp_path / "asap7_tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        result = validate_asap7_identifiers(lef_file, tech_lef_file)
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "is_valid" in result_dict
        assert "pdk_name" in result_dict
        assert "checks_performed" in result_dict
        assert "errors" in result_dict
        assert "warnings" in result_dict
        assert "metadata" in result_dict


class TestValidatePDKFiles:
    """Tests for validate_pdk_files function."""

    def test_validate_pdk_files_asap7_with_valid_files(self, tmp_path):
        """Step 1: Load ASAP7 PDK files from container."""
        # Create LEF with correct ASAP7 site
        lef_content = """
SITE asap7sc7p5t_28_R_24_NP_162NW_34O
  CLASS CORE ;
END asap7sc7p5t_28_R_24_NP_162NW_34O
"""
        lef_file = tmp_path / "asap7.lef"
        lef_file.write_text(lef_content)

        # Create tech LEF with correct metal layers
        tech_lef_content = """
LAYER metal2
  TYPE ROUTING ;
END metal2

LAYER metal3
  TYPE ROUTING ;
END metal3

LAYER metal4
  TYPE ROUTING ;
END metal4

LAYER metal5
  TYPE ROUTING ;
END metal5

LAYER metal6
  TYPE ROUTING ;
END metal6

LAYER metal7
  TYPE ROUTING ;
END metal7

LAYER metal8
  TYPE ROUTING ;
END metal8

LAYER metal9
  TYPE ROUTING ;
END metal9
"""
        tech_lef_file = tmp_path / "asap7_tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        result = validate_pdk_files("asap7", lef_file, tech_lef_file)

        assert result.is_valid is True
        assert result.pdk_name == "asap7"

    def test_validate_pdk_files_asap7_missing_paths(self):
        """Validate ASAP7 without paths returns error."""
        result = validate_pdk_files("asap7")

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("lef_path and tech_lef_path" in error for error in result.errors)

    def test_validate_pdk_files_nangate45_no_validation(self):
        """Validate Nangate45 returns valid (no validation rules)."""
        result = validate_pdk_files("nangate45")

        assert result.is_valid is True
        assert result.pdk_name == "nangate45"
        assert "no_validation_required" in result.checks_performed
        assert len(result.warnings) > 0

    def test_validate_pdk_files_sky130_no_validation(self):
        """Validate Sky130 returns valid (no validation rules)."""
        result = validate_pdk_files("sky130")

        assert result.is_valid is True
        assert result.pdk_name == "sky130"
        assert "no_validation_required" in result.checks_performed

    def test_validate_pdk_files_unknown_pdk(self):
        """Validate unknown PDK returns valid with warning."""
        result = validate_pdk_files("unknown_pdk")

        assert result.is_valid is True
        assert result.pdk_name == "unknown_pdk"
        assert len(result.warnings) > 0
        assert any("Unknown PDK" in warning for warning in result.warnings)

    def test_validate_pdk_files_case_insensitive(self, tmp_path):
        """Validate PDK name is case-insensitive."""
        # Test that ASAP7, asap7, AsAp7 all work
        result1 = validate_pdk_files("ASAP7")
        result2 = validate_pdk_files("asap7")
        result3 = validate_pdk_files("AsAp7")

        # All should be recognized as ASAP7 (and fail because no paths provided)
        assert result1.is_valid is False
        assert result2.is_valid is False
        assert result3.is_valid is False


class TestEndToEndValidation:
    """End-to-end tests for PDK validation workflow."""

    def test_complete_asap7_validation_workflow(self, tmp_path):
        """Complete workflow: parse files, validate, check results."""
        # Step 1: Create mock ASAP7 files
        lef_content = """
VERSION 5.8 ;
BUSBITCHARS "[]" ;

SITE asap7sc7p5t_28_R_24_NP_162NW_34O
  CLASS CORE ;
  SYMMETRY Y ;
  SIZE 0.054 BY 0.270 ;
END asap7sc7p5t_28_R_24_NP_162NW_34O

MACRO example_cell
  CLASS CORE ;
  ORIGIN 0 0 ;
  FOREIGN example_cell 0 0 ;
  SITE asap7sc7p5t_28_R_24_NP_162NW_34O ;
END example_cell
"""
        lef_file = tmp_path / "asap7.lef"
        lef_file.write_text(lef_content)

        tech_lef_content = """
VERSION 5.8 ;

LAYER metal1
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
END metal1

LAYER metal2
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
END metal2

LAYER metal3
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
END metal3

LAYER metal4
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
END metal4

LAYER metal5
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
END metal5

LAYER metal6
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
END metal6

LAYER metal7
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
END metal7

LAYER metal8
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
END metal8

LAYER metal9
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
END metal9
"""
        tech_lef_file = tmp_path / "asap7_tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        # Step 2: Parse files
        sites = parse_lef_sites(lef_file)
        layers = parse_tech_lef_layers(tech_lef_file)

        # Step 3: Verify expected identifiers
        assert "asap7sc7p5t_28_R_24_NP_162NW_34O" in sites
        assert all(f"metal{i}" in layers for i in range(2, 10))

        # Step 4: Run validation
        result = validate_pdk_files("asap7", lef_file, tech_lef_file)

        # Step 5: Check validation passed
        assert result.is_valid is True
        assert len(result.errors) == 0

        # Step 6: Verify metadata is complete
        assert result.metadata["site_validated"] == "asap7sc7p5t_28_R_24_NP_162NW_34O"
        assert len(result.metadata["metal_layers_validated"]) == 8

    def test_asap7_validation_fails_fast_on_mismatch(self, tmp_path):
        """Validation fails fast when identifiers don't match."""
        # Create LEF with wrong site name
        lef_content = """
SITE wrong_site_name
  CLASS CORE ;
END wrong_site_name
"""
        lef_file = tmp_path / "asap7.lef"
        lef_file.write_text(lef_content)

        # Create tech LEF with incomplete metal layers
        tech_lef_content = """
LAYER metal2
  TYPE ROUTING ;
END metal2

LAYER metal3
  TYPE ROUTING ;
END metal3
"""
        tech_lef_file = tmp_path / "asap7_tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        # Run validation
        result = validate_pdk_files("asap7", lef_file, tech_lef_file)

        # Should fail with clear errors
        assert result.is_valid is False
        assert len(result.errors) >= 2  # At least site error and metal layers error

        # Errors should mention expected values
        error_text = " ".join(result.errors)
        assert "asap7sc7p5t_28_R_24_NP_162NW_34O" in error_text
        assert "metal" in error_text.lower()

    def test_validation_result_serialization(self, tmp_path):
        """Validation result can be serialized for logging."""
        lef_content = """
SITE asap7sc7p5t_28_R_24_NP_162NW_34O
  CLASS CORE ;
END asap7sc7p5t_28_R_24_NP_162NW_34O
"""
        lef_file = tmp_path / "asap7.lef"
        lef_file.write_text(lef_content)

        tech_lef_content = """
LAYER metal2
  TYPE ROUTING ;
END metal2
"""
        tech_lef_file = tmp_path / "asap7_tech.lef"
        tech_lef_file.write_text(tech_lef_content)

        result = validate_pdk_files("asap7", lef_file, tech_lef_file)
        result_dict = result.to_dict()

        # Should be JSON-serializable
        import json
        json_str = json.dumps(result_dict)
        assert json_str is not None

        # Should round-trip
        loaded_dict = json.loads(json_str)
        assert loaded_dict["pdk_name"] == "asap7"
        assert "checks_performed" in loaded_dict
