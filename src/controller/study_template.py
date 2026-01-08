"""Study template system for rapid configuration."""

import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .study import load_study_config
from .types import StudyConfig


@dataclass
class TemplateParameter:
    """A parameter in a Study template."""

    name: str
    description: str
    default: Any = None
    required: bool = True

    def __post_init__(self) -> None:
        """Validate parameter configuration."""
        if not self.name:
            raise ValueError("Parameter name cannot be empty")
        if not self.name.isidentifier():
            raise ValueError(f"Parameter name must be a valid identifier: {self.name}")
        if self.required and self.default is not None:
            raise ValueError(f"Required parameter '{self.name}' cannot have a default value")


@dataclass
class StudyTemplate:
    """A parameterized Study template."""

    name: str
    description: str
    parameters: list[TemplateParameter]
    template_yaml: str  # YAML template with {{param}} placeholders
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate template."""
        if not self.name:
            raise ValueError("Template name cannot be empty")
        if not self.template_yaml:
            raise ValueError("Template YAML cannot be empty")

    def get_parameter(self, name: str) -> TemplateParameter | None:
        """Get parameter by name.

        Args:
            name: Parameter name

        Returns:
            TemplateParameter if found, None otherwise
        """
        for param in self.parameters:
            if param.name == name:
                return param
        return None

    def list_parameters(self) -> list[str]:
        """List all parameter names."""
        return [p.name for p in self.parameters]

    def instantiate(self, parameters: dict[str, Any]) -> str:
        """Instantiate template with provided parameters.

        Args:
            parameters: Dictionary of parameter values

        Returns:
            YAML string with parameters substituted

        Raises:
            ValueError: If required parameters are missing or unknown parameters provided
        """
        # Validate all required parameters are provided
        missing = []
        for param in self.parameters:
            if param.required and param.name not in parameters:
                missing.append(param.name)

        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")

        # Check for unknown parameters
        known = set(self.list_parameters())
        provided = set(parameters.keys())
        unknown = provided - known
        if unknown:
            raise ValueError(f"Unknown parameters: {', '.join(sorted(unknown))}")

        # Substitute parameters
        result = self.template_yaml
        for param_name, param_value in parameters.items():
            placeholder = f"{{{{{param_name}}}}}"
            # Convert value to string representation suitable for YAML
            value_str = _format_value_for_yaml(param_value)
            result = result.replace(placeholder, value_str)

        # Check if any parameters remain unsubstituted
        remaining = re.findall(r'\{\{(\w+)\}\}', result)
        if remaining:
            # These are parameters with defaults or optional parameters
            for param_name in remaining:
                param = self.get_parameter(param_name)
                if param and param.default is not None:
                    placeholder = f"{{{{{param_name}}}}}"
                    value_str = _format_value_for_yaml(param.default)
                    result = result.replace(placeholder, value_str)

        # Final check for unsubstituted parameters
        remaining = re.findall(r'\{\{(\w+)\}\}', result)
        if remaining:
            raise ValueError(f"Unsubstituted parameters: {', '.join(remaining)}")

        return result

    def instantiate_to_config(self, parameters: dict[str, Any]) -> StudyConfig:
        """Instantiate template and parse into StudyConfig.

        Args:
            parameters: Dictionary of parameter values

        Returns:
            StudyConfig object

        Raises:
            ValueError: If parameters are invalid or YAML is malformed
        """
        yaml_str = self.instantiate(parameters)

        # Parse YAML
        data = yaml.safe_load(yaml_str)
        if not data:
            raise ValueError("Template produced empty YAML")

        # Import here to avoid circular dependency
        from .study import _parse_study_config

        return _parse_study_config(data)

    def save(self, path: str | Path) -> None:
        """Save template to YAML file.

        Args:
            path: Path to save template
        """
        path = Path(path)

        template_data = {
            "name": self.name,
            "description": self.description,
            "metadata": self.metadata,
            "parameters": [
                {
                    "name": p.name,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                }
                for p in self.parameters
            ],
            "template": self.template_yaml,
        }

        with open(path, 'w') as f:
            yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load(cls, path: str | Path) -> "StudyTemplate":
        """Load template from YAML file.

        Args:
            path: Path to template file

        Returns:
            StudyTemplate object

        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If template is malformed
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Template file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("Empty template file")

        # Parse parameters
        parameters = []
        for param_data in data.get("parameters", []):
            param = TemplateParameter(
                name=param_data["name"],
                description=param_data["description"],
                required=param_data.get("required", True),
                default=param_data.get("default"),
            )
            parameters.append(param)

        return cls(
            name=data["name"],
            description=data["description"],
            parameters=parameters,
            template_yaml=data["template"],
            metadata=data.get("metadata", {}),
        )


def _format_value_for_yaml(value: Any) -> str:
    """Format a Python value for YAML substitution.

    Args:
        value: The value to format

    Returns:
        String representation suitable for YAML
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        # If string contains special characters, quote it
        if any(c in value for c in ['\n', ':', '{', '}', '[', ']', ',', '&', '*', '#', '?', '|', '-', '<', '>', '=', '!', '%', '@', '`']):
            # Escape quotes and wrap in quotes
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'
        return value
    elif isinstance(value, list):
        # Simple list representation
        items = [_format_value_for_yaml(item) for item in value]
        return f"[{', '.join(items)}]"
    elif isinstance(value, dict):
        # Not recommended for inline substitution, but basic support
        return str(value)
    else:
        return str(value)


def create_template_from_study(
    study_config: StudyConfig,
    template_name: str,
    description: str,
    parameters_to_extract: dict[str, str],
) -> StudyTemplate:
    """Create a template from an existing Study configuration.

    Args:
        study_config: The Study configuration to templatize
        template_name: Name for the template
        description: Description of the template
        parameters_to_extract: Dict mapping parameter names to field paths
            e.g., {"pdk": "pdk", "trial_budget": "stages[0].trial_budget"}

    Returns:
        StudyTemplate object

    Raises:
        ValueError: If field paths are invalid
    """
    # Convert StudyConfig to dict for manipulation
    # This is a simplified version - production code would use proper serialization
    raise NotImplementedError(
        "create_template_from_study requires StudyConfig serialization - "
        "use manual template creation for now"
    )


# Built-in templates
def get_nangate45_template() -> StudyTemplate:
    """Get built-in Nangate45 Study template.

    Returns:
        StudyTemplate for Nangate45 studies
    """
    return StudyTemplate(
        name="nangate45_study",
        description="Standard Nangate45 Study with configurable stages",
        parameters=[
            TemplateParameter(
                name="study_name",
                description="Name of the Study",
                required=True
            ),
            TemplateParameter(
                name="snapshot_path",
                description="Path to design snapshot",
                required=True
            ),
            TemplateParameter(
                name="trial_budget",
                description="Number of trials per stage",
                default=10,
                required=False
            ),
            TemplateParameter(
                name="survivor_count",
                description="Number of survivors per stage",
                default=5,
                required=False
            ),
        ],
        template_yaml="""name: {{study_name}}
safety_domain: sandbox
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: {{snapshot_path}}
stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: {{trial_budget}}
    survivor_count: {{survivor_count}}
    allowed_eco_classes: []
""",
        metadata={
            "pdk": "Nangate45",
            "category": "built-in"
        }
    )
