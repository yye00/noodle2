"""OpenROAD-flow-scripts (ORFS) verification utilities.

This module provides functions to verify that:
1. ORFS repository is cloned
2. Required PDK platforms are available (Nangate45, ASAP7, Sky130)
3. Required design files exist
4. ORFS structure is valid
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Default ORFS installation path
DEFAULT_ORFS_PATH = Path("./orfs")


@dataclass
class PlatformVerificationResult:
    """Result of PDK platform verification."""

    platform_name: str
    available: bool
    path: Optional[Path] = None
    error: Optional[str] = None


@dataclass
class DesignVerificationResult:
    """Result of design verification."""

    design_name: str
    platform: str
    available: bool
    path: Optional[Path] = None
    config_exists: bool = False
    error: Optional[str] = None


@dataclass
class ORFSVerificationResult:
    """Complete ORFS installation verification result."""

    orfs_cloned: bool
    orfs_path: Optional[Path] = None
    platforms_available: dict[str, bool] = None
    designs_available: dict[str, bool] = None
    errors: list[str] = None

    def __post_init__(self) -> None:
        if self.platforms_available is None:
            self.platforms_available = {}
        if self.designs_available is None:
            self.designs_available = {}
        if self.errors is None:
            self.errors = []

    @property
    def all_checks_passed(self) -> bool:
        """Check if all verification checks passed."""
        return (
            self.orfs_cloned
            and all(self.platforms_available.values())
            and all(self.designs_available.values())
            and len(self.errors) == 0
        )


def check_orfs_cloned(orfs_path: Path = DEFAULT_ORFS_PATH) -> bool:
    """Check if ORFS repository is cloned.

    Args:
        orfs_path: Path to ORFS installation (default: ./orfs)

    Returns:
        True if ORFS is cloned, False otherwise.
    """
    if not orfs_path.exists():
        return False

    # Check for key ORFS directories
    flow_path = orfs_path / "flow"
    if not flow_path.exists():
        return False

    platforms_path = flow_path / "platforms"
    designs_path = flow_path / "designs"

    return platforms_path.exists() and designs_path.exists()


def verify_platform(
    platform_name: str, orfs_path: Path = DEFAULT_ORFS_PATH
) -> PlatformVerificationResult:
    """Verify that a PDK platform exists in ORFS.

    Args:
        platform_name: Name of the platform (e.g., 'nangate45', 'asap7', 'sky130hd')
        orfs_path: Path to ORFS installation (default: ./orfs)

    Returns:
        PlatformVerificationResult with availability status.
    """
    platforms_path = orfs_path / "flow" / "platforms" / platform_name

    if not platforms_path.exists():
        return PlatformVerificationResult(
            platform_name=platform_name,
            available=False,
            error=f"Platform directory not found: {platforms_path}",
        )

    if not platforms_path.is_dir():
        return PlatformVerificationResult(
            platform_name=platform_name,
            available=False,
            error=f"Platform path is not a directory: {platforms_path}",
        )

    return PlatformVerificationResult(
        platform_name=platform_name, available=True, path=platforms_path
    )


def verify_design(
    design_name: str, platform: str, orfs_path: Path = DEFAULT_ORFS_PATH
) -> DesignVerificationResult:
    """Verify that a design exists for a given platform.

    Args:
        design_name: Name of the design (e.g., 'gcd', 'ibex')
        platform: Platform name (e.g., 'nangate45', 'asap7')
        orfs_path: Path to ORFS installation (default: ./orfs)

    Returns:
        DesignVerificationResult with availability status.
    """
    design_path = orfs_path / "flow" / "designs" / platform / design_name

    if not design_path.exists():
        return DesignVerificationResult(
            design_name=design_name,
            platform=platform,
            available=False,
            error=f"Design directory not found: {design_path}",
        )

    if not design_path.is_dir():
        return DesignVerificationResult(
            design_name=design_name,
            platform=platform,
            available=False,
            error=f"Design path is not a directory: {design_path}",
        )

    # Check for config.mk file
    config_path = design_path / "config.mk"
    config_exists = config_path.exists()

    return DesignVerificationResult(
        design_name=design_name,
        platform=platform,
        available=True,
        path=design_path,
        config_exists=config_exists,
    )


def get_available_platforms(
    orfs_path: Path = DEFAULT_ORFS_PATH,
) -> list[str]:
    """Get list of available platforms in ORFS.

    Args:
        orfs_path: Path to ORFS installation (default: ./orfs)

    Returns:
        List of platform names.
    """
    platforms_path = orfs_path / "flow" / "platforms"

    if not platforms_path.exists():
        return []

    return [
        p.name
        for p in platforms_path.iterdir()
        if p.is_dir() and p.name != "common"
    ]


def get_available_designs(
    platform: str, orfs_path: Path = DEFAULT_ORFS_PATH
) -> list[str]:
    """Get list of available designs for a platform.

    Args:
        platform: Platform name (e.g., 'nangate45')
        orfs_path: Path to ORFS installation (default: ./orfs)

    Returns:
        List of design names.
    """
    designs_path = orfs_path / "flow" / "designs" / platform

    if not designs_path.exists():
        return []

    return [d.name for d in designs_path.iterdir() if d.is_dir()]


def verify_orfs_installation(
    orfs_path: Path = DEFAULT_ORFS_PATH,
    required_platforms: list[str] | None = None,
    required_designs: dict[str, list[str]] | None = None,
) -> ORFSVerificationResult:
    """Perform complete verification of ORFS installation.

    Args:
        orfs_path: Path to ORFS installation (default: ./orfs)
        required_platforms: List of required platform names
            (default: ['nangate45', 'asap7', 'sky130hd'])
        required_designs: Dict mapping platform to list of required designs
            (default: {'nangate45': ['gcd']})

    Returns:
        ORFSVerificationResult with complete status.
    """
    if required_platforms is None:
        required_platforms = ["nangate45", "asap7", "sky130hd"]

    if required_designs is None:
        required_designs = {"nangate45": ["gcd"]}

    errors = []
    platforms_available = {}
    designs_available = {}

    # Check if ORFS is cloned
    orfs_cloned = check_orfs_cloned(orfs_path)
    if not orfs_cloned:
        errors.append(f"ORFS not cloned at {orfs_path}")
        return ORFSVerificationResult(
            orfs_cloned=False,
            orfs_path=orfs_path,
            platforms_available=platforms_available,
            designs_available=designs_available,
            errors=errors,
        )

    # Verify required platforms
    for platform in required_platforms:
        result = verify_platform(platform, orfs_path)
        platforms_available[platform] = result.available
        if not result.available:
            errors.append(f"Platform {platform}: {result.error}")

    # Verify required designs
    for platform, design_list in required_designs.items():
        for design in design_list:
            design_key = f"{platform}/{design}"
            result = verify_design(design, platform, orfs_path)
            designs_available[design_key] = result.available
            if not result.available:
                errors.append(f"Design {design_key}: {result.error}")

    return ORFSVerificationResult(
        orfs_cloned=orfs_cloned,
        orfs_path=orfs_path,
        platforms_available=platforms_available,
        designs_available=designs_available,
        errors=errors,
    )
