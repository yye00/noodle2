"""Tests for ECO framework."""

import pytest

from src.controller.eco import (
    BufferInsertionECO,
    ECO,
    ECOEffectiveness,
    ECOMetadata,
    ECOPrior,
    ECOResult,
    NoOpECO,
    PlacementDensityECO,
    create_eco,
)
from src.controller.types import ECOClass


class TestECOMetadata:
    """Tests for ECO metadata."""

    def test_create_eco_metadata(self) -> None:
        """Test creating ECO metadata."""
        metadata = ECOMetadata(
            name="test_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Test ECO for validation",
        )
        assert metadata.name == "test_eco"
        assert metadata.eco_class == ECOClass.PLACEMENT_LOCAL
        assert metadata.description == "Test ECO for validation"
        assert metadata.version == "1.0"
        assert metadata.parameters == {}

    def test_eco_metadata_with_parameters(self) -> None:
        """Test ECO metadata with parameters."""
        metadata = ECOMetadata(
            name="buffer_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Buffer insertion",
            parameters={"max_cap": 0.5, "buffer_type": "BUF_X4"},
            version="2.0",
            author="test_author",
            tags=["timing", "buffering"],
        )
        assert metadata.parameters["max_cap"] == 0.5
        assert metadata.version == "2.0"
        assert metadata.author == "test_author"
        assert "timing" in metadata.tags

    def test_eco_metadata_validation(self) -> None:
        """Test ECO metadata validation."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            ECOMetadata(
                name="",
                eco_class=ECOClass.TOPOLOGY_NEUTRAL,
                description="Test",
            )

        with pytest.raises(ValueError, match="description cannot be empty"):
            ECOMetadata(
                name="test",
                eco_class=ECOClass.TOPOLOGY_NEUTRAL,
                description="",
            )


class TestECOResult:
    """Tests for ECO results."""

    def test_create_eco_result(self) -> None:
        """Test creating ECO result."""
        result = ECOResult(
            eco_name="test_eco",
            success=True,
            metrics_delta={"wns_improvement_ps": 100},
        )
        assert result.eco_name == "test_eco"
        assert result.success is True
        assert result.metrics_delta["wns_improvement_ps"] == 100

    def test_eco_result_to_dict(self) -> None:
        """Test ECO result serialization."""
        result = ECOResult(
            eco_name="buffer_eco",
            success=True,
            metrics_delta={"wns_ps": 50, "tns_ps": 100},
            execution_time_seconds=1.5,
            artifacts_generated=["timing.rpt", "congestion.rpt"],
        )
        result_dict = result.to_dict()
        assert result_dict["eco_name"] == "buffer_eco"
        assert result_dict["success"] is True
        assert result_dict["metrics_delta"]["wns_ps"] == 50
        assert result_dict["execution_time_seconds"] == 1.5
        assert len(result_dict["artifacts_generated"]) == 2


class TestECOEffectiveness:
    """Tests for ECO effectiveness tracking."""

    def test_create_eco_effectiveness(self) -> None:
        """Test creating ECO effectiveness tracker."""
        effectiveness = ECOEffectiveness(eco_name="test_eco")
        assert effectiveness.eco_name == "test_eco"
        assert effectiveness.total_applications == 0
        assert effectiveness.prior == ECOPrior.UNKNOWN

    def test_update_with_successful_application(self) -> None:
        """Test updating effectiveness with successful application."""
        effectiveness = ECOEffectiveness(eco_name="buffer_eco")
        effectiveness.update(success=True, wns_delta_ps=100)

        assert effectiveness.total_applications == 1
        assert effectiveness.successful_applications == 1
        assert effectiveness.failed_applications == 0
        assert effectiveness.average_wns_improvement_ps == 100
        assert effectiveness.best_wns_improvement_ps == 100

    def test_update_with_failed_application(self) -> None:
        """Test updating effectiveness with failed application."""
        effectiveness = ECOEffectiveness(eco_name="test_eco")
        effectiveness.update(success=False, wns_delta_ps=-50)

        assert effectiveness.total_applications == 1
        assert effectiveness.successful_applications == 0
        assert effectiveness.failed_applications == 1
        assert effectiveness.worst_wns_degradation_ps == -50

    def test_prior_updates_to_trusted(self) -> None:
        """Test prior updates to TRUSTED with good evidence."""
        effectiveness = ECOEffectiveness(eco_name="good_eco")

        # Add multiple successful applications with improvements
        for _ in range(5):
            effectiveness.update(success=True, wns_delta_ps=100)

        assert effectiveness.prior == ECOPrior.TRUSTED
        assert effectiveness.successful_applications == 5

    def test_prior_updates_to_suspicious(self) -> None:
        """Test prior updates to SUSPICIOUS with bad evidence."""
        effectiveness = ECOEffectiveness(eco_name="bad_eco")

        # Add multiple failed applications
        for _ in range(5):
            effectiveness.update(success=False, wns_delta_ps=-100)

        assert effectiveness.prior == ECOPrior.SUSPICIOUS
        assert effectiveness.failed_applications == 5

    def test_prior_updates_to_mixed(self) -> None:
        """Test prior updates to MIXED with mixed evidence."""
        effectiveness = ECOEffectiveness(eco_name="mixed_eco")

        # Add mix of successes and failures
        effectiveness.update(success=True, wns_delta_ps=50)
        effectiveness.update(success=False, wns_delta_ps=-30)
        effectiveness.update(success=True, wns_delta_ps=60)

        assert effectiveness.prior == ECOPrior.MIXED

    def test_prior_remains_unknown_with_insufficient_data(self) -> None:
        """Test prior remains UNKNOWN with < 3 applications."""
        effectiveness = ECOEffectiveness(eco_name="new_eco")

        effectiveness.update(success=True, wns_delta_ps=100)
        effectiveness.update(success=True, wns_delta_ps=50)

        assert effectiveness.total_applications == 2
        assert effectiveness.prior == ECOPrior.UNKNOWN

    def test_effectiveness_to_dict(self) -> None:
        """Test effectiveness serialization."""
        effectiveness = ECOEffectiveness(eco_name="test_eco")
        effectiveness.update(success=True, wns_delta_ps=100)
        effectiveness.update(success=True, wns_delta_ps=50)

        eff_dict = effectiveness.to_dict()
        assert eff_dict["eco_name"] == "test_eco"
        assert eff_dict["total_applications"] == 2
        assert eff_dict["successful_applications"] == 2
        assert eff_dict["success_rate"] == 1.0
        assert "average_wns_improvement_ps" in eff_dict


class TestNoOpECO:
    """Tests for No-Op ECO."""

    def test_create_noop_eco(self) -> None:
        """Test creating no-op ECO."""
        eco = NoOpECO()
        assert eco.name == "noop"
        assert eco.eco_class == ECOClass.TOPOLOGY_NEUTRAL
        assert eco.metadata.description == "No-operation ECO for baseline testing"

    def test_noop_generate_tcl(self) -> None:
        """Test no-op ECO generates empty script."""
        eco = NoOpECO()
        tcl = eco.generate_tcl()
        assert "No-op" in tcl
        assert tcl.strip().startswith("#")

    def test_noop_validate_parameters(self) -> None:
        """Test no-op ECO parameters always valid."""
        eco = NoOpECO()
        assert eco.validate_parameters() is True

    def test_noop_to_dict(self) -> None:
        """Test no-op ECO serialization."""
        eco = NoOpECO()
        eco_dict = eco.to_dict()
        assert eco_dict["name"] == "noop"
        assert eco_dict["eco_class"] == "topology_neutral"


class TestBufferInsertionECO:
    """Tests for Buffer Insertion ECO."""

    def test_create_buffer_insertion_eco(self) -> None:
        """Test creating buffer insertion ECO."""
        eco = BufferInsertionECO(max_capacitance=0.3, buffer_cell="BUF_X8")
        assert eco.name == "buffer_insertion"
        assert eco.eco_class == ECOClass.PLACEMENT_LOCAL
        assert eco.metadata.parameters["max_capacitance"] == 0.3
        assert eco.metadata.parameters["buffer_cell"] == "BUF_X8"

    def test_buffer_insertion_default_parameters(self) -> None:
        """Test buffer insertion with default parameters."""
        eco = BufferInsertionECO()
        assert eco.metadata.parameters["max_capacitance"] == 0.2
        assert eco.metadata.parameters["buffer_cell"] == "BUF_X4"

    def test_buffer_insertion_generate_tcl(self) -> None:
        """Test buffer insertion generates valid Tcl."""
        eco = BufferInsertionECO(max_capacitance=0.25)
        tcl = eco.generate_tcl()
        assert "Buffer Insertion ECO" in tcl
        assert "0.25" in tcl
        assert "repair_design" in tcl

    def test_buffer_insertion_validate_parameters(self) -> None:
        """Test buffer insertion parameter validation."""
        eco = BufferInsertionECO(max_capacitance=0.2, buffer_cell="BUF_X4")
        assert eco.validate_parameters() is True

        # Test invalid parameters
        eco.metadata.parameters["max_capacitance"] = -1
        assert eco.validate_parameters() is False

        eco.metadata.parameters["max_capacitance"] = 0.2
        eco.metadata.parameters["buffer_cell"] = ""
        assert eco.validate_parameters() is False

    def test_buffer_insertion_tags(self) -> None:
        """Test buffer insertion has correct tags."""
        eco = BufferInsertionECO()
        assert "timing_optimization" in eco.metadata.tags
        assert "buffering" in eco.metadata.tags


class TestPlacementDensityECO:
    """Tests for Placement Density ECO."""

    def test_create_placement_density_eco(self) -> None:
        """Test creating placement density ECO."""
        eco = PlacementDensityECO(target_density=0.6)
        assert eco.name == "placement_density"
        assert eco.eco_class == ECOClass.ROUTING_AFFECTING
        assert eco.metadata.parameters["target_density"] == 0.6

    def test_placement_density_default_parameters(self) -> None:
        """Test placement density with default parameters."""
        eco = PlacementDensityECO()
        assert eco.metadata.parameters["target_density"] == 0.7

    def test_placement_density_generate_tcl(self) -> None:
        """Test placement density generates valid Tcl."""
        eco = PlacementDensityECO(target_density=0.65)
        tcl = eco.generate_tcl()
        assert "Placement Density ECO" in tcl
        assert "0.65" in tcl
        assert "global_placement" in tcl
        assert "detailed_placement" in tcl

    def test_placement_density_validate_parameters(self) -> None:
        """Test placement density parameter validation."""
        eco = PlacementDensityECO(target_density=0.7)
        assert eco.validate_parameters() is True

        # Test invalid parameters
        eco.metadata.parameters["target_density"] = 0
        assert eco.validate_parameters() is False

        eco.metadata.parameters["target_density"] = 1.5
        assert eco.validate_parameters() is False

    def test_placement_density_tags(self) -> None:
        """Test placement density has correct tags."""
        eco = PlacementDensityECO()
        assert "congestion_reduction" in eco.metadata.tags
        assert "placement" in eco.metadata.tags


class TestECOFactory:
    """Tests for ECO factory."""

    def test_create_noop_eco(self) -> None:
        """Test creating no-op ECO via factory."""
        eco = create_eco("noop")
        assert isinstance(eco, NoOpECO)
        assert eco.name == "noop"

    def test_create_buffer_insertion_eco(self) -> None:
        """Test creating buffer insertion ECO via factory."""
        eco = create_eco("buffer_insertion", max_capacitance=0.3, buffer_cell="BUF_X8")
        assert isinstance(eco, BufferInsertionECO)
        assert eco.metadata.parameters["max_capacitance"] == 0.3

    def test_create_placement_density_eco(self) -> None:
        """Test creating placement density ECO via factory."""
        eco = create_eco("placement_density", target_density=0.6)
        assert isinstance(eco, PlacementDensityECO)
        assert eco.metadata.parameters["target_density"] == 0.6

    def test_create_unknown_eco_raises_error(self) -> None:
        """Test creating unknown ECO raises error."""
        with pytest.raises(ValueError, match="Unknown ECO"):
            create_eco("nonexistent_eco")


class TestECOComparability:
    """Tests for ECO comparability across cases and studies."""

    def test_eco_name_is_stable(self) -> None:
        """Test ECO names are stable across multiple instantiations."""
        eco1 = NoOpECO()
        eco2 = NoOpECO()
        assert eco1.name == eco2.name

        eco3 = BufferInsertionECO()
        eco4 = BufferInsertionECO()
        assert eco3.name == eco4.name

    def test_eco_classification_determines_safety_constraints(self) -> None:
        """Test ECO classification determines safety constraints."""
        noop = NoOpECO()
        assert noop.eco_class == ECOClass.TOPOLOGY_NEUTRAL

        buffer = BufferInsertionECO()
        assert buffer.eco_class == ECOClass.PLACEMENT_LOCAL

        placement = PlacementDensityECO()
        assert placement.eco_class == ECOClass.ROUTING_AFFECTING

    def test_eco_serialization_enables_comparison(self) -> None:
        """Test ECO serialization enables cross-case comparison."""
        eco1 = BufferInsertionECO(max_capacitance=0.25)
        eco2 = BufferInsertionECO(max_capacitance=0.25)

        dict1 = eco1.to_dict()
        dict2 = eco2.to_dict()

        # Same ECO with same parameters should serialize identically
        assert dict1["name"] == dict2["name"]
        assert dict1["eco_class"] == dict2["eco_class"]
        assert dict1["parameters"] == dict2["parameters"]
