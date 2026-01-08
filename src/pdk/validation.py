"""PDK validation utilities to verify expected identifiers and file formats."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PDKValidationResult:
    """Result of PDK validation checks."""

    is_valid: bool
    pdk_name: str
    checks_performed: list[str]
    errors: list[str]
    warnings: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "pdk_name": self.pdk_name,
            "checks_performed": self.checks_performed,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class PDKValidationError(Exception):
    """Exception raised when PDK validation fails."""

    def __init__(self, message: str, result: PDKValidationResult):
        super().__init__(message)
        self.result = result


def parse_lef_sites(lef_path: str | Path) -> list[str]:
    """
    Parse LEF file to extract SITE names.

    Args:
        lef_path: Path to LEF file

    Returns:
        List of site names found in LEF

    Raises:
        FileNotFoundError: If LEF file doesn't exist
        ValueError: If LEF file cannot be parsed
    """
    lef_path = Path(lef_path)
    if not lef_path.exists():
        raise FileNotFoundError(f"LEF file not found: {lef_path}")

    sites = []

    try:
        with open(lef_path, 'r') as f:
            content = f.read()

        # Match SITE definitions: SITE sitename
        # Example: SITE asap7sc7p5t_28_R_24_NP_162NW_34O
        site_pattern = r'^\s*SITE\s+(\S+)\s*$'

        for match in re.finditer(site_pattern, content, re.MULTILINE):
            site_name = match.group(1)
            sites.append(site_name)

    except Exception as e:
        raise ValueError(f"Failed to parse LEF file {lef_path}: {e}")

    return sites


def parse_tech_lef_layers(lef_path: str | Path) -> list[str]:
    """
    Parse technology LEF file to extract metal layer names.

    Args:
        lef_path: Path to technology LEF file

    Returns:
        List of metal layer names (e.g., ['metal1', 'metal2', ...])

    Raises:
        FileNotFoundError: If tech LEF file doesn't exist
        ValueError: If tech LEF file cannot be parsed
    """
    lef_path = Path(lef_path)
    if not lef_path.exists():
        raise FileNotFoundError(f"Tech LEF file not found: {lef_path}")

    layers = []

    try:
        with open(lef_path, 'r') as f:
            content = f.read()

        # Match LAYER definitions: LAYER layername
        # Example: LAYER metal2
        # We're interested in ROUTING layers (metal layers)
        layer_pattern = r'^\s*LAYER\s+(metal\d+)\s*$'

        for match in re.finditer(layer_pattern, content, re.MULTILINE | re.IGNORECASE):
            layer_name = match.group(1).lower()
            if layer_name not in layers:  # Avoid duplicates
                layers.append(layer_name)

    except Exception as e:
        raise ValueError(f"Failed to parse tech LEF file {lef_path}: {e}")

    # Sort metal layers numerically
    layers.sort(key=lambda x: int(re.search(r'\d+', x).group()))

    return layers


def validate_asap7_identifiers(
    lef_path: str | Path,
    tech_lef_path: str | Path,
) -> PDKValidationResult:
    """
    Validate ASAP7 LEF/tech files match expected identifiers.

    Checks:
    - Site name matches asap7sc7p5t_28_R_24_NP_162NW_34O
    - Metal layers include metal2 through metal9

    Args:
        lef_path: Path to ASAP7 LEF file
        tech_lef_path: Path to ASAP7 technology LEF file

    Returns:
        PDKValidationResult with validation status
    """
    pdk_name = "asap7"
    checks_performed = []
    errors = []
    warnings = []
    metadata = {}

    # Expected identifiers for ASAP7
    expected_site = "asap7sc7p5t_28_R_24_NP_162NW_34O"
    expected_metal_layers = ["metal2", "metal3", "metal4", "metal5",
                             "metal6", "metal7", "metal8", "metal9"]

    # Check 1: Parse and validate LEF site names
    checks_performed.append("parse_lef_sites")
    try:
        sites = parse_lef_sites(lef_path)
        metadata["sites_found"] = sites

        if expected_site not in sites:
            errors.append(
                f"Expected ASAP7 site '{expected_site}' not found in LEF. "
                f"Found sites: {sites}"
            )
        else:
            metadata["site_validated"] = expected_site

    except Exception as e:
        errors.append(f"Failed to parse LEF sites: {e}")

    # Check 2: Parse and validate tech LEF metal layers
    checks_performed.append("parse_tech_lef_layers")
    try:
        layers = parse_tech_lef_layers(tech_lef_path)
        metadata["metal_layers_found"] = layers

        # Check if expected metal layers are present
        missing_layers = [layer for layer in expected_metal_layers
                          if layer not in layers]

        if missing_layers:
            errors.append(
                f"Expected ASAP7 metal layers missing: {missing_layers}. "
                f"Found layers: {layers}"
            )
        else:
            metadata["metal_layers_validated"] = expected_metal_layers

        # Check if there are extra layers (not an error, but worth noting)
        extra_layers = [layer for layer in layers
                        if layer not in expected_metal_layers and layer.startswith('metal')]
        if extra_layers:
            warnings.append(
                f"Additional metal layers found beyond expected range: {extra_layers}"
            )

    except Exception as e:
        errors.append(f"Failed to parse tech LEF layers: {e}")

    is_valid = len(errors) == 0

    return PDKValidationResult(
        is_valid=is_valid,
        pdk_name=pdk_name,
        checks_performed=checks_performed,
        errors=errors,
        warnings=warnings,
        metadata=metadata,
    )


def validate_pdk_files(
    pdk: str,
    lef_path: str | Path | None = None,
    tech_lef_path: str | Path | None = None,
) -> PDKValidationResult:
    """
    Validate PDK files match expected identifiers.

    Currently supports:
    - ASAP7: Validates site name and metal layer naming
    - Other PDKs: Returns valid (no validation implemented yet)

    Args:
        pdk: PDK name ('nangate45', 'asap7', 'sky130')
        lef_path: Optional path to LEF file (required for ASAP7)
        tech_lef_path: Optional path to tech LEF file (required for ASAP7)

    Returns:
        PDKValidationResult with validation status

    Raises:
        PDKValidationError: If validation fails and strict mode is enabled
    """
    pdk_lower = pdk.lower()

    if pdk_lower == "asap7":
        if not lef_path or not tech_lef_path:
            result = PDKValidationResult(
                is_valid=False,
                pdk_name=pdk,
                checks_performed=[],
                errors=["ASAP7 validation requires both lef_path and tech_lef_path"],
                warnings=[],
                metadata={},
            )
            return result

        return validate_asap7_identifiers(lef_path, tech_lef_path)

    elif pdk_lower in ["nangate45", "sky130"]:
        # No specific validation for these PDKs yet
        return PDKValidationResult(
            is_valid=True,
            pdk_name=pdk,
            checks_performed=["no_validation_required"],
            errors=[],
            warnings=[f"No validation rules defined for {pdk} (assumed valid)"],
            metadata={"validation_skipped": True},
        )

    else:
        # Unknown PDK
        return PDKValidationResult(
            is_valid=True,
            pdk_name=pdk,
            checks_performed=["unknown_pdk"],
            errors=[],
            warnings=[f"Unknown PDK '{pdk}', no validation performed"],
            metadata={"validation_skipped": True},
        )
