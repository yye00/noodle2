"""Tests for F258: ECO definition supports parameterized TCL templates."""

import pytest
from controller.eco import ECOMetadata
from controller.eco_templates import ParameterDefinition, ParameterizedECO
from controller.types import ECOClass


class TestF258ParameterizedTCLTemplates:
    """Test parameterized TCL template support for ECOs."""

    def test_step_1_define_eco_with_tcl_template_containing_placeholders(self):
        """Step 1: Define ECO with tcl_template containing {{ parameter }} placeholders."""
        # Define a TCL template with parameter placeholders
        template = """
# Buffer insertion ECO
set max_cap {{ max_capacitance }}
set buffer_cell {{ buffer_cell }}

# Find high-capacitance nets
set high_cap_nets [get_nets -filter "capacitance > $max_cap"]

# Insert buffers on each net
foreach net $high_cap_nets {
    insert_buffer -net $net -cell $buffer_cell
}
"""

        # Create ECO with template
        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="parameterized_buffer_insertion",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Buffer insertion with configurable parameters",
            ),
            tcl_template=template,
        )

        assert eco.tcl_template == template
        assert eco.name == "parameterized_buffer_insertion"

    def test_step_2_define_parameters_with_type_default_and_range(self):
        """Step 2: Define parameters with type, default, and range."""
        # Define parameters with types, defaults, and ranges
        params = {
            "max_capacitance": ParameterDefinition(
                name="max_capacitance",
                param_type="float",
                default=0.2,
                min_value=0.01,
                max_value=1.0,
                description="Maximum net capacitance threshold (pF)",
            ),
            "buffer_cell": ParameterDefinition(
                name="buffer_cell",
                param_type="str",
                default="BUF_X4",
                allowed_values=["BUF_X2", "BUF_X4", "BUF_X8"],
                description="Buffer cell to insert",
            ),
        }

        template = "set max_cap {{ max_capacitance }}\nset buf {{ buffer_cell }}"

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        assert "max_capacitance" in eco.parameters
        assert eco.parameters["max_capacitance"].default == 0.2
        assert eco.parameters["max_capacitance"].min_value == 0.01
        assert eco.parameters["max_capacitance"].max_value == 1.0

        assert "buffer_cell" in eco.parameters
        assert eco.parameters["buffer_cell"].default == "BUF_X4"
        assert eco.parameters["buffer_cell"].allowed_values == ["BUF_X2", "BUF_X4", "BUF_X8"]

    def test_step_3_apply_eco_with_custom_parameter_values(self):
        """Step 3: Apply ECO with custom parameter values."""
        params = {
            "max_capacitance": ParameterDefinition(
                name="max_capacitance",
                param_type="float",
                default=0.2,
                min_value=0.01,
                max_value=1.0,
            ),
        }

        template = "set max_cap {{ max_capacitance }}"

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        # Generate TCL with custom parameter values
        tcl = eco.generate_tcl(max_capacitance=0.5)

        assert "set max_cap 0.5" in tcl

    def test_step_4_verify_tcl_template_is_rendered_with_parameter_substitution(self):
        """Step 4: Verify TCL template is rendered with parameter substitution."""
        params = {
            "max_capacitance": ParameterDefinition(
                name="max_capacitance",
                param_type="float",
                default=0.2,
            ),
            "buffer_cell": ParameterDefinition(
                name="buffer_cell",
                param_type="str",
                default="BUF_X4",
            ),
            "threshold": ParameterDefinition(
                name="threshold",
                param_type="int",
                default=100,
            ),
        }

        template = """
set max_cap {{ max_capacitance }}
set buffer {{ buffer_cell }}
set thresh {{ threshold }}
"""

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        # Generate with custom values
        tcl = eco.generate_tcl(
            max_capacitance=0.35,
            buffer_cell="BUF_X8",
            threshold=250,
        )

        # Verify all substitutions happened
        assert "set max_cap 0.35" in tcl
        assert "set buffer BUF_X8" in tcl
        assert "set thresh 250" in tcl

        # Verify no placeholders remain
        assert "{{" not in tcl
        assert "}}" not in tcl

    def test_step_5_verify_parameters_are_within_defined_ranges(self):
        """Step 5: Verify parameters are within defined ranges."""
        params = {
            "max_capacitance": ParameterDefinition(
                name="max_capacitance",
                param_type="float",
                default=0.2,
                min_value=0.01,
                max_value=1.0,
            ),
        }

        template = "set max_cap {{ max_capacitance }}"

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        # Valid parameter should work
        assert eco.validate_parameters(max_capacitance=0.5) is True

        # Edge cases should work
        assert eco.validate_parameters(max_capacitance=0.01) is True
        assert eco.validate_parameters(max_capacitance=1.0) is True

    def test_step_6_verify_out_of_range_parameters_are_rejected(self):
        """Step 6: Verify out-of-range parameters are rejected."""
        params = {
            "max_capacitance": ParameterDefinition(
                name="max_capacitance",
                param_type="float",
                default=0.2,
                min_value=0.01,
                max_value=1.0,
            ),
        }

        template = "set max_cap {{ max_capacitance }}"

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        # Below minimum should be rejected
        assert eco.validate_parameters(max_capacitance=0.001) is False

        # Above maximum should be rejected
        assert eco.validate_parameters(max_capacitance=2.0) is False


class TestParameterDefinitionDetails:
    """Test ParameterDefinition class in detail."""

    def test_parameter_with_numeric_range(self):
        """Test parameter definition with numeric range."""
        param = ParameterDefinition(
            name="threshold",
            param_type="float",
            default=0.5,
            min_value=0.0,
            max_value=1.0,
            description="Threshold value",
        )

        assert param.name == "threshold"
        assert param.param_type == "float"
        assert param.default == 0.5
        assert param.min_value == 0.0
        assert param.max_value == 1.0

    def test_parameter_with_allowed_values(self):
        """Test parameter definition with allowed values."""
        param = ParameterDefinition(
            name="strategy",
            param_type="str",
            default="aggressive",
            allowed_values=["conservative", "balanced", "aggressive"],
            description="Optimization strategy",
        )

        assert param.allowed_values == ["conservative", "balanced", "aggressive"]
        assert param.default == "aggressive"

    def test_parameter_validation_numeric_range(self):
        """Test numeric range validation."""
        param = ParameterDefinition(
            name="value",
            param_type="float",
            default=50.0,
            min_value=0.0,
            max_value=100.0,
        )

        # Valid values
        assert param.validate(50.0) is True
        assert param.validate(0.0) is True
        assert param.validate(100.0) is True
        assert param.validate(25.5) is True

        # Invalid values
        assert param.validate(-1.0) is False
        assert param.validate(101.0) is False

    def test_parameter_validation_allowed_values(self):
        """Test allowed values validation."""
        param = ParameterDefinition(
            name="mode",
            param_type="str",
            default="normal",
            allowed_values=["slow", "normal", "fast"],
        )

        # Valid values
        assert param.validate("slow") is True
        assert param.validate("normal") is True
        assert param.validate("fast") is True

        # Invalid values
        assert param.validate("turbo") is False
        assert param.validate("") is False

    def test_parameter_type_coercion(self):
        """Test parameter type coercion."""
        # Integer parameter
        int_param = ParameterDefinition(
            name="count",
            param_type="int",
            default=10,
        )

        # Should coerce float to int
        assert int_param.validate(10.0) is True

        # Float parameter
        float_param = ParameterDefinition(
            name="ratio",
            param_type="float",
            default=0.5,
        )

        # Should accept int as float
        assert float_param.validate(1) is True


class TestParameterizedECOEdgeCases:
    """Test edge cases for parameterized ECOs."""

    def test_generate_tcl_with_defaults(self):
        """Test generating TCL with default parameter values."""
        params = {
            "max_cap": ParameterDefinition(
                name="max_cap",
                param_type="float",
                default=0.2,
            ),
            "buffer": ParameterDefinition(
                name="buffer",
                param_type="str",
                default="BUF_X4",
            ),
        }

        template = "set max_cap {{ max_cap }}\nset buffer {{ buffer }}"

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        # Generate with no overrides - should use defaults
        tcl = eco.generate_tcl()

        assert "set max_cap 0.2" in tcl
        assert "set buffer BUF_X4" in tcl

    def test_generate_tcl_with_partial_overrides(self):
        """Test generating TCL with some parameters overridden."""
        params = {
            "max_cap": ParameterDefinition(
                name="max_cap",
                param_type="float",
                default=0.2,
            ),
            "buffer": ParameterDefinition(
                name="buffer",
                param_type="str",
                default="BUF_X4",
            ),
        }

        template = "set max_cap {{ max_cap }}\nset buffer {{ buffer }}"

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        # Override only one parameter
        tcl = eco.generate_tcl(max_cap=0.5)

        assert "set max_cap 0.5" in tcl
        assert "set buffer BUF_X4" in tcl  # Should use default

    def test_missing_parameter_in_template(self):
        """Test handling of parameters not in template."""
        params = {
            "max_cap": ParameterDefinition(
                name="max_cap",
                param_type="float",
                default=0.2,
            ),
        }

        template = "# No placeholders here"

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        # Should generate without error
        tcl = eco.generate_tcl()
        assert tcl == template

    def test_undefined_parameter_in_template(self):
        """Test handling of placeholders without parameter definitions."""
        params = {}

        template = "set max_cap {{ max_cap }}"

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        # Should raise error when trying to generate
        with pytest.raises(ValueError, match="Undefined parameter"):
            eco.generate_tcl()

    def test_serialization_to_dict(self):
        """Test serializing parameterized ECO to dictionary."""
        params = {
            "max_cap": ParameterDefinition(
                name="max_cap",
                param_type="float",
                default=0.2,
                min_value=0.01,
                max_value=1.0,
            ),
        }

        template = "set max_cap {{ max_cap }}"

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        eco_dict = eco.to_dict()

        assert eco_dict["name"] == "test_eco"
        assert eco_dict["tcl_template"] == template
        assert "parameters" in eco_dict
        assert "max_cap" in eco_dict["parameters"]


class TestComplexParameterizedTemplates:
    """Test complex parameterized template scenarios."""

    def test_multi_line_template_with_many_parameters(self):
        """Test complex template with many parameters."""
        params = {
            "max_capacitance": ParameterDefinition(
                name="max_capacitance",
                param_type="float",
                default=0.2,
                min_value=0.01,
                max_value=1.0,
            ),
            "min_slack": ParameterDefinition(
                name="min_slack",
                param_type="float",
                default=-100.0,
                min_value=-1000.0,
                max_value=0.0,
            ),
            "buffer_cell": ParameterDefinition(
                name="buffer_cell",
                param_type="str",
                default="BUF_X4",
                allowed_values=["BUF_X2", "BUF_X4", "BUF_X8"],
            ),
            "max_fanout": ParameterDefinition(
                name="max_fanout",
                param_type="int",
                default=16,
                min_value=1,
                max_value=64,
            ),
        }

        template = """
# Advanced buffer insertion ECO
set max_cap {{ max_capacitance }}
set min_slack {{ min_slack }}
set buffer {{ buffer_cell }}
set max_fo {{ max_fanout }}

# Find problematic nets
set bad_nets [get_nets -filter "capacitance > $max_cap || slack < $min_slack"]

# Process each net
foreach net $bad_nets {
    set fanout [get_property $net fanout]
    if {$fanout > $max_fo} {
        insert_buffer -net $net -cell $buffer
    }
}
"""

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="advanced_buffer_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Advanced buffer insertion",
            ),
            tcl_template=template,
            parameters=params,
        )

        tcl = eco.generate_tcl(
            max_capacitance=0.3,
            min_slack=-200.0,
            buffer_cell="BUF_X8",
            max_fanout=32,
        )

        assert "set max_cap 0.3" in tcl
        assert "set min_slack -200.0" in tcl
        assert "set buffer BUF_X8" in tcl
        assert "set max_fo 32" in tcl
        assert "{{" not in tcl

    def test_template_with_repeated_parameters(self):
        """Test template with same parameter used multiple times."""
        params = {
            "buffer_cell": ParameterDefinition(
                name="buffer_cell",
                param_type="str",
                default="BUF_X4",
            ),
        }

        template = """
set primary_buffer {{ buffer_cell }}
set secondary_buffer {{ buffer_cell }}
insert_buffer -cell {{ buffer_cell }}
"""

        eco = ParameterizedECO(
            metadata=ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
            ),
            tcl_template=template,
            parameters=params,
        )

        tcl = eco.generate_tcl(buffer_cell="BUF_X8")

        # All occurrences should be replaced
        assert tcl.count("BUF_X8") == 3
        assert "{{" not in tcl
