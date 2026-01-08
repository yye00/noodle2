"""Tests for Study template system."""

import tempfile
from pathlib import Path

import pytest

from src.controller.study_template import (
    StudyTemplate,
    TemplateParameter,
    get_nangate45_template,
    _format_value_for_yaml,
)


class TestTemplateParameter:
    """Tests for TemplateParameter."""

    def test_create_required_parameter(self) -> None:
        """Test creating a required parameter."""
        param = TemplateParameter(
            name="pdk",
            description="PDK to use",
            required=True
        )
        assert param.name == "pdk"
        assert param.description == "PDK to use"
        assert param.required is True
        assert param.default is None

    def test_create_optional_parameter(self) -> None:
        """Test creating an optional parameter with default."""
        param = TemplateParameter(
            name="trial_budget",
            description="Number of trials",
            required=False,
            default=10
        )
        assert param.name == "trial_budget"
        assert param.required is False
        assert param.default == 10

    def test_invalid_parameter_name(self) -> None:
        """Test that invalid parameter names raise error."""
        with pytest.raises(ValueError, match="valid identifier"):
            TemplateParameter(
                name="invalid-name",  # Hyphens not allowed
                description="Test"
            )

    def test_empty_parameter_name(self) -> None:
        """Test that empty parameter name raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            TemplateParameter(
                name="",
                description="Test"
            )

    def test_required_with_default_error(self) -> None:
        """Test that required parameter with default raises error."""
        with pytest.raises(ValueError, match="cannot have a default"):
            TemplateParameter(
                name="test",
                description="Test",
                required=True,
                default="value"
            )


class TestStudyTemplate:
    """Tests for StudyTemplate."""

    def test_create_minimal_template(self) -> None:
        """Test creating a minimal template."""
        template = StudyTemplate(
            name="test_template",
            description="Test template",
            parameters=[],
            template_yaml="name: test\npdk: Nangate45"
        )
        assert template.name == "test_template"
        assert template.description == "Test template"
        assert len(template.parameters) == 0

    def test_create_template_with_parameters(self) -> None:
        """Test creating template with parameters."""
        params = [
            TemplateParameter(name="study_name", description="Study name", required=True),
            TemplateParameter(name="pdk", description="PDK", required=True),
        ]
        template = StudyTemplate(
            name="test_template",
            description="Test",
            parameters=params,
            template_yaml="name: {{study_name}}\npdk: {{pdk}}"
        )
        assert len(template.parameters) == 2
        assert template.list_parameters() == ["study_name", "pdk"]

    def test_get_parameter(self) -> None:
        """Test getting parameter by name."""
        params = [
            TemplateParameter(name="pdk", description="PDK", required=True),
        ]
        template = StudyTemplate(
            name="test",
            description="Test",
            parameters=params,
            template_yaml="pdk: {{pdk}}"
        )
        param = template.get_parameter("pdk")
        assert param is not None
        assert param.name == "pdk"

        missing = template.get_parameter("nonexistent")
        assert missing is None

    def test_instantiate_simple(self) -> None:
        """Test instantiating template with parameters."""
        template = StudyTemplate(
            name="test",
            description="Test",
            parameters=[
                TemplateParameter(name="study_name", description="Study name", required=True),
                TemplateParameter(name="pdk", description="PDK", required=True),
            ],
            template_yaml="name: {{study_name}}\npdk: {{pdk}}"
        )

        result = template.instantiate({
            "study_name": "my_study",
            "pdk": "Nangate45"
        })

        assert "name: my_study" in result
        assert "pdk: Nangate45" in result
        assert "{{" not in result  # No placeholders remaining

    def test_instantiate_with_default(self) -> None:
        """Test instantiating template with default parameters."""
        template = StudyTemplate(
            name="test",
            description="Test",
            parameters=[
                TemplateParameter(name="study_name", description="Study name", required=True),
                TemplateParameter(name="trial_budget", description="Trials", required=False, default=10),
            ],
            template_yaml="name: {{study_name}}\ntrial_budget: {{trial_budget}}"
        )

        # Don't provide optional parameter - should use default
        result = template.instantiate({
            "study_name": "my_study"
        })

        assert "name: my_study" in result
        assert "trial_budget: 10" in result

    def test_instantiate_missing_required(self) -> None:
        """Test that missing required parameters raise error."""
        template = StudyTemplate(
            name="test",
            description="Test",
            parameters=[
                TemplateParameter(name="required_param", description="Required", required=True),
            ],
            template_yaml="value: {{required_param}}"
        )

        with pytest.raises(ValueError, match="Missing required parameters"):
            template.instantiate({})

    def test_instantiate_unknown_parameter(self) -> None:
        """Test that unknown parameters raise error."""
        template = StudyTemplate(
            name="test",
            description="Test",
            parameters=[
                TemplateParameter(name="known", description="Known", required=True),
            ],
            template_yaml="value: {{known}}"
        )

        with pytest.raises(ValueError, match="Unknown parameters"):
            template.instantiate({
                "known": "value",
                "unknown": "bad"
            })

    def test_instantiate_multiple_occurrences(self) -> None:
        """Test substituting parameters that appear multiple times."""
        template = StudyTemplate(
            name="test",
            description="Test",
            parameters=[
                TemplateParameter(name="pdk", description="PDK", required=True),
            ],
            template_yaml="""
pdk: {{pdk}}
metadata:
  pdk_used: {{pdk}}
"""
        )

        result = template.instantiate({"pdk": "Nangate45"})
        assert result.count("Nangate45") == 2
        assert "{{pdk}}" not in result

    def test_save_and_load_template(self) -> None:
        """Test saving and loading template from file."""
        template = StudyTemplate(
            name="test_template",
            description="Test template for saving",
            parameters=[
                TemplateParameter(name="study_name", description="Study name", required=True),
                TemplateParameter(name="budget", description="Budget", required=False, default=10),
            ],
            template_yaml="name: {{study_name}}\nbudget: {{budget}}",
            metadata={"author": "test"}
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            template_path = f.name

        try:
            # Save
            template.save(template_path)

            # Load
            loaded = StudyTemplate.load(template_path)

            assert loaded.name == template.name
            assert loaded.description == template.description
            assert len(loaded.parameters) == len(template.parameters)
            assert loaded.template_yaml == template.template_yaml
            assert loaded.metadata == template.metadata

            # Verify parameters
            param1 = loaded.get_parameter("study_name")
            assert param1 is not None
            assert param1.required is True

            param2 = loaded.get_parameter("budget")
            assert param2 is not None
            assert param2.default == 10

        finally:
            Path(template_path).unlink()

    def test_load_missing_file(self) -> None:
        """Test loading non-existent template raises error."""
        with pytest.raises(FileNotFoundError):
            StudyTemplate.load("/nonexistent/template.yaml")


class TestFormatValueForYAML:
    """Tests for YAML value formatting."""

    def test_format_bool(self) -> None:
        """Test formatting boolean values."""
        assert _format_value_for_yaml(True) == "true"
        assert _format_value_for_yaml(False) == "false"

    def test_format_int(self) -> None:
        """Test formatting integer values."""
        assert _format_value_for_yaml(42) == "42"
        assert _format_value_for_yaml(0) == "0"
        assert _format_value_for_yaml(-10) == "-10"

    def test_format_float(self) -> None:
        """Test formatting float values."""
        assert _format_value_for_yaml(3.14) == "3.14"
        assert _format_value_for_yaml(0.0) == "0.0"

    def test_format_simple_string(self) -> None:
        """Test formatting simple strings."""
        assert _format_value_for_yaml("hello") == "hello"
        assert _format_value_for_yaml("Nangate45") == "Nangate45"

    def test_format_string_with_special_chars(self) -> None:
        """Test formatting strings with special characters."""
        result = _format_value_for_yaml("value: test")
        assert result.startswith('"')
        assert result.endswith('"')

    def test_format_list(self) -> None:
        """Test formatting lists."""
        result = _format_value_for_yaml([1, 2, 3])
        assert "[" in result and "]" in result
        assert "1" in result and "2" in result and "3" in result


class TestBuiltInTemplates:
    """Tests for built-in templates."""

    def test_nangate45_template(self) -> None:
        """Test Nangate45 built-in template."""
        template = get_nangate45_template()

        assert template.name == "nangate45_study"
        assert "Nangate45" in template.description
        assert len(template.parameters) == 4

        # Check required parameters
        study_name_param = template.get_parameter("study_name")
        assert study_name_param is not None
        assert study_name_param.required is True

        snapshot_param = template.get_parameter("snapshot_path")
        assert snapshot_param is not None
        assert snapshot_param.required is True

        # Check optional parameters with defaults
        budget_param = template.get_parameter("trial_budget")
        assert budget_param is not None
        assert budget_param.required is False
        assert budget_param.default == 10

    def test_instantiate_nangate45_template(self) -> None:
        """Test instantiating Nangate45 template."""
        template = get_nangate45_template()

        yaml_str = template.instantiate({
            "study_name": "nangate45_test",
            "snapshot_path": "/path/to/snapshot",
        })

        assert "name: nangate45_test" in yaml_str
        assert "snapshot_path: /path/to/snapshot" in yaml_str
        assert "trial_budget: 10" in yaml_str  # Default
        assert "survivor_count: 5" in yaml_str  # Default
        assert "pdk: Nangate45" in yaml_str

    def test_instantiate_nangate45_with_overrides(self) -> None:
        """Test instantiating Nangate45 template with custom values."""
        template = get_nangate45_template()

        yaml_str = template.instantiate({
            "study_name": "custom_study",
            "snapshot_path": "/custom/path",
            "trial_budget": 20,
            "survivor_count": 10,
        })

        assert "trial_budget: 20" in yaml_str
        assert "survivor_count: 10" in yaml_str


class TestTemplateIntegration:
    """Integration tests for template system."""

    def test_instantiate_to_config(self) -> None:
        """Test instantiating template to StudyConfig."""
        template = get_nangate45_template()

        config = template.instantiate_to_config({
            "study_name": "integration_test",
            "snapshot_path": "/path/to/snapshot",
        })

        assert config.name == "integration_test"
        assert config.pdk == "Nangate45"
        assert config.snapshot_path == "/path/to/snapshot"
        assert len(config.stages) == 1
        assert config.stages[0].trial_budget == 10  # Default

    def test_instantiate_to_config_with_custom_values(self) -> None:
        """Test instantiating template with custom values to StudyConfig."""
        template = get_nangate45_template()

        config = template.instantiate_to_config({
            "study_name": "custom_test",
            "snapshot_path": "/custom/path",
            "trial_budget": 25,
            "survivor_count": 15,
        })

        assert config.stages[0].trial_budget == 25
        assert config.stages[0].survivor_count == 15

    def test_full_workflow_save_load_instantiate(self) -> None:
        """Test complete workflow: create, save, load, instantiate."""
        # Create template
        template = StudyTemplate(
            name="workflow_test",
            description="Full workflow test",
            parameters=[
                TemplateParameter(name="name", description="Name", required=True),
                TemplateParameter(name="pdk", description="PDK", required=True),
            ],
            template_yaml="""name: {{name}}
safety_domain: sandbox
base_case_name: base
pdk: {{pdk}}
snapshot_path: /path
stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes: []
"""
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            template_path = f.name

        try:
            # Save template
            template.save(template_path)

            # Load template
            loaded_template = StudyTemplate.load(template_path)

            # Instantiate to config
            config = loaded_template.instantiate_to_config({
                "name": "final_test",
                "pdk": "Nangate45"
            })

            # Verify config
            assert config.name == "final_test"
            assert config.pdk == "Nangate45"
            assert config.safety_domain.value == "sandbox"

        finally:
            Path(template_path).unlink()
