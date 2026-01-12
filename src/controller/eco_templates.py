"""Parameterized ECO template support for Noodle 2.

This module provides support for defining ECOs with parameterized TCL templates,
enabling reusable ECO definitions with configurable parameters.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from .eco import ECO, ECOMetadata


@dataclass
class ParameterDefinition:
    """Definition of a parameter for a parameterized ECO.

    Parameters can have types, default values, ranges, and allowed values.
    """

    name: str
    param_type: str  # "int", "float", "str", "bool"
    default: Any
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: list[Any] | None = None
    description: str = ""

    def validate(self, value: Any) -> bool:
        """Validate a value against this parameter's constraints.

        Args:
            value: The value to validate

        Returns:
            True if valid, False otherwise
        """
        # Check allowed values if specified
        if self.allowed_values is not None:
            return value in self.allowed_values

        # Check numeric range if specified
        if self.min_value is not None or self.max_value is not None:
            try:
                # Coerce to appropriate type
                if self.param_type == "int":
                    numeric_value = int(value)
                elif self.param_type == "float":
                    numeric_value = float(value)
                else:
                    # Non-numeric types don't have range validation
                    return True

                # Check min
                if self.min_value is not None and numeric_value < self.min_value:
                    return False

                # Check max
                if self.max_value is not None and numeric_value > self.max_value:
                    return False

                return True
            except (ValueError, TypeError):
                return False

        # No constraints, always valid
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.param_type,
            "default": self.default,
        }

        if self.min_value is not None:
            result["min_value"] = self.min_value

        if self.max_value is not None:
            result["max_value"] = self.max_value

        if self.allowed_values is not None:
            result["allowed_values"] = self.allowed_values

        if self.description:
            result["description"] = self.description

        return result


class ParameterizedECO(ECO):
    """ECO with parameterized TCL template support.

    This class enables defining ECOs with TCL templates containing
    {{ parameter }} placeholders that are substituted with actual
    values at generation time.

    Example:
        >>> params = {
        ...     "max_cap": ParameterDefinition(
        ...         name="max_cap",
        ...         param_type="float",
        ...         default=0.2,
        ...         min_value=0.01,
        ...         max_value=1.0,
        ...     ),
        ... }
        >>> template = "set max_capacitance {{ max_cap }}"
        >>> eco = ParameterizedECO(
        ...     metadata=ECOMetadata(...),
        ...     tcl_template=template,
        ...     parameters=params,
        ... )
        >>> tcl = eco.generate_tcl(max_cap=0.5)
        >>> # tcl == "set max_capacitance 0.5"
    """

    def __init__(
        self,
        metadata: ECOMetadata,
        tcl_template: str,
        parameters: dict[str, ParameterDefinition] | None = None,
    ) -> None:
        """Initialize parameterized ECO.

        Args:
            metadata: ECO metadata
            tcl_template: TCL template with {{ parameter }} placeholders
            parameters: Dictionary of parameter definitions
        """
        super().__init__(metadata)
        self.tcl_template = tcl_template
        self.parameters = parameters or {}

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script by substituting parameters into template.

        Args:
            **kwargs: Parameter values to use (overrides defaults)

        Returns:
            TCL script with parameters substituted

        Raises:
            ValueError: If template references undefined parameters
        """
        # Merge kwargs with defaults
        param_values = self._merge_parameter_values(kwargs)

        # Substitute parameters into template
        result = self.tcl_template

        # Find all {{ parameter }} placeholders
        placeholders = re.findall(r"\{\{\s*(\w+)\s*\}\}", result)

        for placeholder in placeholders:
            if placeholder not in param_values:
                raise ValueError(
                    f"Undefined parameter '{placeholder}' in template. "
                    f"Available parameters: {list(self.parameters.keys())}"
                )

            # Get the value and substitute
            value = param_values[placeholder]
            pattern = r"\{\{\s*" + re.escape(placeholder) + r"\s*\}\}"
            result = re.sub(pattern, str(value), result)

        return result

    def validate_parameters(self, **kwargs: Any) -> bool:
        """Validate parameter values against constraints.

        Args:
            **kwargs: Parameter values to validate

        Returns:
            True if all parameters are valid, False otherwise
        """
        # Merge with defaults
        param_values = self._merge_parameter_values(kwargs)

        # Validate each parameter
        for name, value in param_values.items():
            if name not in self.parameters:
                # Unknown parameter, but we'll allow it for flexibility
                continue

            param_def = self.parameters[name]
            if not param_def.validate(value):
                return False

        return True

    def _merge_parameter_values(self, overrides: dict[str, Any]) -> dict[str, Any]:
        """Merge override values with defaults.

        Args:
            overrides: Parameter values to override defaults

        Returns:
            Dictionary with merged values (overrides + defaults)
        """
        # Start with defaults
        result = {}
        for name, param_def in self.parameters.items():
            result[name] = param_def.default

        # Apply overrides
        result.update(overrides)

        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        base_dict = super().to_dict()
        base_dict["tcl_template"] = self.tcl_template
        base_dict["parameters"] = {
            name: param.to_dict() for name, param in self.parameters.items()
        }
        return base_dict
