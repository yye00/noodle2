"""
Feature list loader and validator.

This module provides functionality to load and validate the feature_list.json
file at runtime for test tracking purposes.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FeatureDefinition:
    """
    Represents a single feature from the feature list.

    Attributes:
        category: Feature category (functional or style)
        description: Human-readable feature description
        steps: List of test steps for this feature
        passes: Whether this feature currently passes all tests
    """

    category: str
    description: str
    steps: list[str]
    passes: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureDefinition":
        """Create a FeatureDefinition from a dictionary."""
        return cls(
            category=data["category"],
            description=data["description"],
            steps=data["steps"],
            passes=data.get("passes", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "category": self.category,
            "description": self.description,
            "steps": self.steps,
            "passes": self.passes,
        }


def load_feature_list(feature_list_path: Path | str | None = None) -> list[FeatureDefinition]:
    """
    Load feature list from JSON file.

    Args:
        feature_list_path: Path to feature_list.json. If None, looks in project root.

    Returns:
        List of FeatureDefinition objects

    Raises:
        FileNotFoundError: If feature_list.json is not found
        json.JSONDecodeError: If JSON is invalid
        ValueError: If feature list structure is invalid
    """
    if feature_list_path is None:
        # Look for feature_list.json in project root (relative to this file)
        this_file = Path(__file__)
        project_root = this_file.parent.parent.parent
        feature_list_path = project_root / "feature_list.json"
    else:
        feature_list_path = Path(feature_list_path)

    if not feature_list_path.exists():
        raise FileNotFoundError(f"Feature list not found at {feature_list_path}")

    with open(feature_list_path, 'r') as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Feature list must be a JSON array")

    features = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Feature {i} is not a dictionary")

        try:
            feature = FeatureDefinition.from_dict(item)
            features.append(feature)
        except KeyError as e:
            raise ValueError(f"Feature {i} is missing required field: {e}")

    return features


def validate_feature_list(features: list[FeatureDefinition]) -> dict[str, Any]:
    """
    Validate feature list structure and requirements.

    Validates:
    - Minimum 200 features present
    - At least 25 features have 10+ steps
    - All features have required fields
    - Categories are valid (functional or style)

    Args:
        features: List of FeatureDefinition objects

    Returns:
        Dictionary with validation results:
        - valid: bool indicating if all validations pass
        - errors: list of error messages
        - warnings: list of warning messages
        - stats: dictionary with feature statistics
    """
    errors = []
    warnings = []

    # Count features
    total_count = len(features)

    # Validate minimum feature count
    if total_count < 200:
        errors.append(f"Feature list has {total_count} features, minimum 200 required")

    # Count features by category
    functional_count = sum(1 for f in features if f.category == "functional")
    style_count = sum(1 for f in features if f.category == "style")

    # Check for invalid categories
    for i, f in enumerate(features):
        if f.category not in ["functional", "style"]:
            errors.append(f"Feature {i} has invalid category: {f.category}")

    # Validate features have steps
    features_without_steps = [i for i, f in enumerate(features) if not f.steps]
    if features_without_steps:
        errors.append(f"{len(features_without_steps)} features have no steps")

    # Count features with 10+ steps
    large_features = [f for f in features if len(f.steps) >= 10]
    if len(large_features) < 25:
        warnings.append(
            f"Only {len(large_features)} features have 10+ steps, "
            f"25 recommended for comprehensive testing"
        )

    # Validate description field is non-empty
    empty_descriptions = [i for i, f in enumerate(features) if not f.description]
    if empty_descriptions:
        errors.append(f"{len(empty_descriptions)} features have empty descriptions")

    # Calculate statistics
    stats = {
        "total_features": total_count,
        "functional_features": functional_count,
        "style_features": style_count,
        "features_with_10plus_steps": len(large_features),
        "passing_features": sum(1 for f in features if f.passes),
        "failing_features": sum(1 for f in features if not f.passes),
        "avg_steps_per_feature": sum(len(f.steps) for f in features) / total_count if total_count > 0 else 0,
        "max_steps_in_feature": max((len(f.steps) for f in features), default=0),
        "min_steps_in_feature": min((len(f.steps) for f in features), default=0),
    }

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
    }
