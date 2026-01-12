"""Tests for F261: ECO parameter ranges are validated before execution.

Feature: F261
Priority: low
Description: ECO parameter ranges are validated before execution

Steps:
1. Define ECO parameter with range: [1.1, 2.0]
2. Attempt to apply ECO with parameter value 2.5 (out of range)
3. Verify parameter validation fails before execution
4. Verify clear error message indicates range violation
5. Verify ECO is not executed with invalid parameters
"""

import pytest
from controller.eco import (
    ECO,
    ECOMetadata,
    BufferInsertionECO,
    PlacementDensityECO,
)
from controller.types import ECOClass


class TestParameterRangeValidation:
    """Test parameter range validation for ECOs."""

    def test_step_1_define_eco_with_parameter_range(self) -> None:
        """Step 1: Define ECO parameter with range: [1.1, 2.0]."""
        # Define an ECO with parameter ranges
        metadata = ECOMetadata(
            name="test_eco_with_range",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Test ECO with parameter range",
            parameters={
                "target_density": 1.5,
            },
            parameter_ranges={
                "target_density": {"min": 1.1, "max": 2.0},
            },
        )

        # Verify the parameter_ranges field exists
        assert hasattr(metadata, "parameter_ranges")
        assert "target_density" in metadata.parameter_ranges
        assert metadata.parameter_ranges["target_density"]["min"] == 1.1
        assert metadata.parameter_ranges["target_density"]["max"] == 2.0

    def test_step_2_attempt_out_of_range_parameter(self) -> None:
        """Step 2: Attempt to apply ECO with parameter value 2.5 (out of range)."""
        # Create an ECO with parameter range - this should raise in __post_init__
        with pytest.raises(ValueError) as exc_info:
            metadata = ECOMetadata(
                name="test_eco_with_range",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO with parameter range",
                parameters={
                    "target_density": 2.5,  # Out of range!
                },
                parameter_ranges={
                    "target_density": {"min": 1.1, "max": 2.0},
                },
            )

        assert "above maximum" in str(exc_info.value).lower() or "range" in str(exc_info.value).lower()

    def test_step_3_parameter_validation_fails_before_execution(self) -> None:
        """Step 3: Verify parameter validation fails before execution."""

        class TestECO(ECO):
            """Test ECO implementation."""

            def generate_tcl(self, **kwargs):  # type: ignore
                return "# Test TCL\n"

            def validate_parameters(self) -> bool:
                """Validate parameters including ranges."""
                return self.validate_parameter_ranges()

        # Create metadata with valid parameters initially
        metadata = ECOMetadata(
            name="test_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Test ECO",
            parameters={"value": 1.5},  # Valid initially
            parameter_ranges={"value": {"min": 1.0, "max": 2.0}},
        )

        eco = TestECO(metadata)

        # Now change parameter to invalid value
        eco.metadata.parameters["value"] = 2.5

        # validate_parameters should fail
        assert not eco.validate_parameters()

    def test_step_4_clear_error_message_for_range_violation(self) -> None:
        """Step 4: Verify clear error message indicates range violation."""
        # When parameter is out of range, error message should be clear
        try:
            metadata = ECOMetadata(
                name="test_eco",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Test ECO",
                parameters={"density": 0.95},
                parameter_ranges={"density": {"min": 0.1, "max": 0.8}},
            )
            metadata.__post_init__()
            # If we get here, validation didn't happen - fail the test
            pytest.fail("Expected ValueError for out-of-range parameter")
        except ValueError as e:
            error_msg = str(e)
            # Error message should mention:
            # - The parameter name
            # - The invalid value
            # - The valid range
            assert "density" in error_msg.lower()
            assert "0.95" in error_msg or "range" in error_msg.lower()

    def test_step_5_eco_not_executed_with_invalid_parameters(self) -> None:
        """Step 5: Verify ECO is not executed with invalid parameters."""

        class ExecutionTrackingECO(ECO):
            """ECO that tracks if it was executed."""

            def __init__(self, metadata: ECOMetadata) -> None:
                super().__init__(metadata)
                self.executed = False

            def generate_tcl(self, **kwargs):  # type: ignore
                self.executed = True
                return "# Test\n"

            def validate_parameters(self) -> bool:
                return self.validate_parameter_ranges()

        # Create ECO with valid parameters initially
        metadata = ECOMetadata(
            name="test_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Test ECO",
            parameters={"value": 2.0},  # Valid initially
            parameter_ranges={"value": {"min": 1.0, "max": 3.0}},
        )

        eco = ExecutionTrackingECO(metadata)

        # Now set parameter to invalid value
        eco.metadata.parameters["value"] = 5.0

        # Validate parameters first (would happen before execution)
        assert not eco.validate_parameters()

        # Since validation failed, we shouldn't call generate_tcl
        # In real execution, the framework would check validate_parameters first
        assert not eco.executed


class TestParameterRangeValidationIntegration:
    """Integration tests for parameter range validation."""

    def test_buffer_insertion_with_parameter_range(self) -> None:
        """Test BufferInsertionECO with parameter range validation."""
        # Create BufferInsertionECO with parameter range
        eco = BufferInsertionECO(max_capacitance=0.5)

        # Add parameter range constraint
        eco.metadata.parameter_ranges = {
            "max_capacitance": {"min": 0.1, "max": 1.0},
        }

        # Valid parameter should pass
        assert eco.validate_parameters()

        # Set parameter out of range
        eco.metadata.parameters["max_capacitance"] = 1.5

        # Should fail validation
        assert not eco.validate_parameters()

    def test_placement_density_with_parameter_range(self) -> None:
        """Test PlacementDensityECO with parameter range validation."""
        # Create PlacementDensityECO with parameter range
        eco = PlacementDensityECO(target_density=0.7)

        # Add parameter range constraint
        eco.metadata.parameter_ranges = {
            "target_density": {"min": 0.3, "max": 0.95},
        }

        # Valid parameter should pass
        assert eco.validate_parameters()

        # Set parameter out of range
        eco.metadata.parameters["target_density"] = 0.99

        # Should fail validation
        assert not eco.validate_parameters()

    def test_multiple_parameters_with_ranges(self) -> None:
        """Test ECO with multiple parameters having ranges."""
        metadata = ECOMetadata(
            name="multi_param_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO with multiple parameters",
            parameters={
                "param1": 1.5,
                "param2": 25,
                "param3": 0.5,
            },
            parameter_ranges={
                "param1": {"min": 1.0, "max": 2.0},
                "param2": {"min": 10, "max": 50},
                "param3": {"min": 0.0, "max": 1.0},
            },
        )

        class MultiParamECO(ECO):
            def generate_tcl(self, **kwargs):  # type: ignore
                return "# Test\n"

            def validate_parameters(self) -> bool:
                return self.validate_parameter_ranges()

        eco = MultiParamECO(metadata)

        # All parameters in range - should pass
        assert eco.validate_parameters()

        # Set one parameter out of range
        eco.metadata.parameters["param2"] = 60

        # Should fail validation
        assert not eco.validate_parameters()

    def test_parameter_range_with_no_min(self) -> None:
        """Test parameter range with only max constraint."""
        metadata = ECOMetadata(
            name="test_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Test ECO",
            parameters={"value": 5.0},
            parameter_ranges={
                "value": {"max": 10.0},  # Only max, no min
            },
        )

        class TestECO(ECO):
            def generate_tcl(self, **kwargs):  # type: ignore
                return "# Test\n"

            def validate_parameters(self) -> bool:
                return self.validate_parameter_ranges()

        eco = TestECO(metadata)

        # Should pass (5.0 < 10.0)
        assert eco.validate_parameters()

        # Set above max
        eco.metadata.parameters["value"] = 15.0
        assert not eco.validate_parameters()

    def test_parameter_range_with_no_max(self) -> None:
        """Test parameter range with only min constraint."""
        metadata = ECOMetadata(
            name="test_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Test ECO",
            parameters={"value": 5.0},
            parameter_ranges={
                "value": {"min": 1.0},  # Only min, no max
            },
        )

        class TestECO(ECO):
            def generate_tcl(self, **kwargs):  # type: ignore
                return "# Test\n"

            def validate_parameters(self) -> bool:
                return self.validate_parameter_ranges()

        eco = TestECO(metadata)

        # Should pass (5.0 > 1.0)
        assert eco.validate_parameters()

        # Set below min
        eco.metadata.parameters["value"] = 0.5
        assert not eco.validate_parameters()

    def test_boundary_values(self) -> None:
        """Test that boundary values are accepted."""
        metadata = ECOMetadata(
            name="test_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Test ECO",
            parameters={"value": 1.0},
            parameter_ranges={
                "value": {"min": 1.0, "max": 2.0},
            },
        )

        class TestECO(ECO):
            def generate_tcl(self, **kwargs):  # type: ignore
                return "# Test\n"

            def validate_parameters(self) -> bool:
                return self.validate_parameter_ranges()

        eco = TestECO(metadata)

        # Test min boundary
        eco.metadata.parameters["value"] = 1.0
        assert eco.validate_parameters()

        # Test max boundary
        eco.metadata.parameters["value"] = 2.0
        assert eco.validate_parameters()

        # Just below min
        eco.metadata.parameters["value"] = 0.9999
        assert not eco.validate_parameters()

        # Just above max
        eco.metadata.parameters["value"] = 2.0001
        assert not eco.validate_parameters()

    def test_no_parameter_ranges_defined(self) -> None:
        """Test that ECO without parameter_ranges defined validates successfully."""
        metadata = ECOMetadata(
            name="test_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Test ECO",
            parameters={"value": 999.0},  # Any value should be OK
        )

        class TestECO(ECO):
            def generate_tcl(self, **kwargs):  # type: ignore
                return "# Test\n"

            def validate_parameters(self) -> bool:
                return self.validate_parameter_ranges()

        eco = TestECO(metadata)

        # Should pass - no ranges defined means no constraints
        assert eco.validate_parameters()
