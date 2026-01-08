"""Tests for ECO parameter sweep functionality."""

import pytest

from src.controller.eco import BufferInsertionECO, PlacementDensityECO, create_eco
from src.controller.parameter_sweep import (
    ParameterRange,
    ParameterSetResult,
    ParameterSweepConfig,
    ParameterSweepResult,
    analyze_sweep_results,
    create_sweep_ecos,
    generate_parameter_sets,
)


class TestParameterRange:
    """Tests for ParameterRange dataclass."""

    def test_create_parameter_range(self) -> None:
        """Test creating a parameter range."""
        param_range = ParameterRange(
            name="max_capacitance", values=[0.1, 0.2, 0.3, 0.4]
        )

        assert param_range.name == "max_capacitance"
        assert param_range.values == [0.1, 0.2, 0.3, 0.4]
        assert param_range.type == "auto"

    def test_parameter_range_with_type(self) -> None:
        """Test parameter range with explicit type."""
        param_range = ParameterRange(name="threshold", values=[10, 20, 30], type="int")

        assert param_range.type == "int"

    def test_parameter_range_validates_name(self) -> None:
        """Test that parameter range validates non-empty name."""
        with pytest.raises(ValueError, match="Parameter name cannot be empty"):
            ParameterRange(name="", values=[1, 2, 3])

    def test_parameter_range_validates_values(self) -> None:
        """Test that parameter range validates non-empty values list."""
        with pytest.raises(ValueError, match="Parameter values list cannot be empty"):
            ParameterRange(name="param", values=[])

    def test_parameter_range_validates_unique_values(self) -> None:
        """Test that parameter range validates unique values."""
        with pytest.raises(ValueError, match="Parameter values must be unique"):
            ParameterRange(name="param", values=[1, 2, 2, 3])


class TestParameterSweepConfig:
    """Tests for ParameterSweepConfig dataclass."""

    def test_create_sweep_config(self) -> None:
        """Test creating a parameter sweep configuration."""
        param_range = ParameterRange(name="max_capacitance", values=[0.1, 0.2, 0.3])

        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range],
            fixed_parameters={"buffer_cell": "BUF_X4"},
            sweep_mode="sequential",
        )

        assert config.eco_name == "buffer_insertion"
        assert len(config.parameter_ranges) == 1
        assert config.fixed_parameters == {"buffer_cell": "BUF_X4"}
        assert config.sweep_mode == "sequential"

    def test_sweep_config_validates_eco_name(self) -> None:
        """Test that sweep config validates non-empty ECO name."""
        param_range = ParameterRange(name="param", values=[1, 2])

        with pytest.raises(ValueError, match="ECO name cannot be empty"):
            ParameterSweepConfig(
                eco_name="", parameter_ranges=[param_range], sweep_mode="sequential"
            )

    def test_sweep_config_validates_parameter_ranges(self) -> None:
        """Test that sweep config validates non-empty parameter ranges."""
        with pytest.raises(ValueError, match="Must specify at least one parameter range"):
            ParameterSweepConfig(
                eco_name="buffer_insertion", parameter_ranges=[], sweep_mode="sequential"
            )

    def test_sweep_config_validates_sweep_mode(self) -> None:
        """Test that sweep config validates sweep mode."""
        param_range = ParameterRange(name="param", values=[1, 2])

        with pytest.raises(ValueError, match="Invalid sweep_mode"):
            ParameterSweepConfig(
                eco_name="buffer_insertion",
                parameter_ranges=[param_range],
                sweep_mode="invalid",
            )

    def test_sweep_config_prevents_overlap_between_swept_and_fixed(self) -> None:
        """Test that sweep config prevents overlap between swept and fixed parameters."""
        param_range = ParameterRange(name="max_capacitance", values=[0.1, 0.2])

        with pytest.raises(
            ValueError, match="Parameters cannot be both swept and fixed"
        ):
            ParameterSweepConfig(
                eco_name="buffer_insertion",
                parameter_ranges=[param_range],
                fixed_parameters={"max_capacitance": 0.5},  # Overlaps with swept param
                sweep_mode="sequential",
            )


class TestSequentialSweepGeneration:
    """Tests for sequential parameter sweep generation."""

    def test_generate_sequential_sweep_single_parameter(self) -> None:
        """Step 1: Define ECO with tunable parameter."""
        param_range = ParameterRange(
            name="max_capacitance", values=[0.1, 0.2, 0.3, 0.4]
        )

        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range],
            fixed_parameters={"buffer_cell": "BUF_X4"},
            sweep_mode="sequential",
        )

        """Step 2: Configure parameter sweep range."""
        parameter_sets = generate_parameter_sets(config)

        """Step 3: Generate trials systematically varying parameter."""
        assert len(parameter_sets) == 4  # One for each value

        # Verify each parameter set
        for i, param_set in enumerate(parameter_sets):
            assert param_set["max_capacitance"] == param_range.values[i]
            assert param_set["buffer_cell"] == "BUF_X4"

    def test_generate_sequential_sweep_multiple_parameters(self) -> None:
        """Test sequential sweep with multiple parameters (varies one at a time)."""
        param_range1 = ParameterRange(name="max_capacitance", values=[0.1, 0.2])
        param_range2 = ParameterRange(name="threshold", values=[5, 10])

        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range1, param_range2],
            sweep_mode="sequential",
        )

        parameter_sets = generate_parameter_sets(config)

        # Sequential: varies max_capacitance (2 values) then threshold (2 values) = 4 total
        assert len(parameter_sets) == 4

        # First 2 vary max_capacitance, threshold stays at baseline (first value)
        assert parameter_sets[0] == {"max_capacitance": 0.1, "threshold": 5}
        assert parameter_sets[1] == {"max_capacitance": 0.2, "threshold": 5}

        # Next 2 vary threshold, max_capacitance stays at baseline (first value)
        assert parameter_sets[2] == {"max_capacitance": 0.1, "threshold": 5}
        assert parameter_sets[3] == {"max_capacitance": 0.1, "threshold": 10}


class TestGridSweepGeneration:
    """Tests for grid parameter sweep generation."""

    def test_generate_grid_sweep_single_parameter(self) -> None:
        """Test grid sweep with single parameter (same as sequential)."""
        param_range = ParameterRange(name="max_capacitance", values=[0.1, 0.2, 0.3])

        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range],
            sweep_mode="grid",
        )

        parameter_sets = generate_parameter_sets(config)

        assert len(parameter_sets) == 3

    def test_generate_grid_sweep_multiple_parameters(self) -> None:
        """Test grid sweep with multiple parameters (Cartesian product)."""
        param_range1 = ParameterRange(name="max_capacitance", values=[0.1, 0.2])
        param_range2 = ParameterRange(name="threshold", values=[5, 10])

        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range1, param_range2],
            sweep_mode="grid",
        )

        parameter_sets = generate_parameter_sets(config)

        # Grid: Cartesian product = 2 * 2 = 4
        assert len(parameter_sets) == 4

        # Verify all combinations exist
        expected_sets = [
            {"max_capacitance": 0.1, "threshold": 5},
            {"max_capacitance": 0.1, "threshold": 10},
            {"max_capacitance": 0.2, "threshold": 5},
            {"max_capacitance": 0.2, "threshold": 10},
        ]

        for expected in expected_sets:
            assert expected in parameter_sets

    def test_generate_grid_sweep_three_parameters(self) -> None:
        """Test grid sweep with three parameters."""
        param_range1 = ParameterRange(name="param1", values=[1, 2])
        param_range2 = ParameterRange(name="param2", values=[3, 4])
        param_range3 = ParameterRange(name="param3", values=[5, 6])

        config = ParameterSweepConfig(
            eco_name="test_eco",
            parameter_ranges=[param_range1, param_range2, param_range3],
            sweep_mode="grid",
        )

        parameter_sets = generate_parameter_sets(config)

        # Grid: 2 * 2 * 2 = 8
        assert len(parameter_sets) == 8


class TestCreateSweepECOs:
    """Tests for creating ECO instances from sweep configuration."""

    def test_create_sweep_ecos(self) -> None:
        """Step 4: Execute all parameter sweep trials."""
        param_range = ParameterRange(name="max_capacitance", values=[0.1, 0.2, 0.3])

        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range],
            fixed_parameters={"buffer_cell": "BUF_X4"},
            sweep_mode="sequential",
        )

        ecos = create_sweep_ecos(config)

        assert len(ecos) == 3

        # Verify each ECO has correct parameters
        for i, eco in enumerate(ecos):
            assert isinstance(eco, BufferInsertionECO)
            assert eco.metadata.parameters["max_capacitance"] == param_range.values[i]
            assert eco.metadata.parameters["buffer_cell"] == "BUF_X4"

    def test_create_sweep_ecos_validates_eco_name(self) -> None:
        """Test that creating sweep ECOs validates ECO name exists."""
        param_range = ParameterRange(name="param", values=[1, 2])

        config = ParameterSweepConfig(
            eco_name="nonexistent_eco",
            parameter_ranges=[param_range],
            sweep_mode="sequential",
        )

        with pytest.raises(ValueError, match="Unknown ECO"):
            create_sweep_ecos(config)


class TestParameterSetResult:
    """Tests for ParameterSetResult dataclass."""

    def test_create_parameter_set_result(self) -> None:
        """Test creating a parameter set result."""
        eco = create_eco("buffer_insertion", max_capacitance=0.2, buffer_cell="BUF_X4")
        parameters = {"max_capacitance": 0.2, "buffer_cell": "BUF_X4"}

        result = ParameterSetResult(
            parameters=parameters,
            eco_instance=eco,
            metrics={"wns_ps": -500, "tns_ps": -5000},
            success=True,
        )

        assert result.parameters == parameters
        assert result.eco_instance == eco
        assert result.metrics["wns_ps"] == -500
        assert result.success is True

    def test_parameter_set_result_to_dict(self) -> None:
        """Test converting parameter set result to dictionary."""
        eco = create_eco("buffer_insertion", max_capacitance=0.2, buffer_cell="BUF_X4")
        parameters = {"max_capacitance": 0.2}

        result = ParameterSetResult(
            parameters=parameters,
            eco_instance=eco,
            metrics={"wns_ps": -500},
            success=True,
        )

        result_dict = result.to_dict()

        assert result_dict["parameters"] == parameters
        assert result_dict["eco_name"] == "buffer_insertion"
        assert result_dict["metrics"]["wns_ps"] == -500
        assert result_dict["success"] is True


class TestParameterSweepAnalysis:
    """Tests for parameter sweep analysis."""

    def test_identify_optimal_parameters(self) -> None:
        """Step 5: Identify optimal parameter value."""
        eco1 = create_eco("buffer_insertion", max_capacitance=0.1)
        eco2 = create_eco("buffer_insertion", max_capacitance=0.2)
        eco3 = create_eco("buffer_insertion", max_capacitance=0.3)

        results = [
            ParameterSetResult(
                parameters={"max_capacitance": 0.1},
                eco_instance=eco1,
                metrics={"wns_ps": -1000},  # Bad
                success=True,
            ),
            ParameterSetResult(
                parameters={"max_capacitance": 0.2},
                eco_instance=eco2,
                metrics={"wns_ps": -200},  # Best (closest to 0)
                success=True,
            ),
            ParameterSetResult(
                parameters={"max_capacitance": 0.3},
                eco_instance=eco3,
                metrics={"wns_ps": -500},  # Medium
                success=True,
            ),
        ]

        param_range = ParameterRange(name="max_capacitance", values=[0.1, 0.2, 0.3])
        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range],
            sweep_mode="sequential",
        )

        sweep_result = analyze_sweep_results(
            sweep_config=config, results=results, metric_name="wns_ps", maximize=True
        )

        # Best WNS is -200 (max/closest to 0)
        assert sweep_result.optimal_parameters == {"max_capacitance": 0.2}

    def test_identify_optimal_parameters_minimize(self) -> None:
        """Test identifying optimal parameters when minimizing metric."""
        eco1 = create_eco("placement_density", target_density=0.6)
        eco2 = create_eco("placement_density", target_density=0.7)

        results = [
            ParameterSetResult(
                parameters={"target_density": 0.6},
                eco_instance=eco1,
                metrics={"congestion_bins_hot": 10},  # Better (lower)
                success=True,
            ),
            ParameterSetResult(
                parameters={"target_density": 0.7},
                eco_instance=eco2,
                metrics={"congestion_bins_hot": 20},  # Worse (higher)
                success=True,
            ),
        ]

        param_range = ParameterRange(name="target_density", values=[0.6, 0.7])
        config = ParameterSweepConfig(
            eco_name="placement_density",
            parameter_ranges=[param_range],
            sweep_mode="sequential",
        )

        sweep_result = analyze_sweep_results(
            sweep_config=config,
            results=results,
            metric_name="congestion_bins_hot",
            maximize=False,  # Minimize congestion
        )

        # Lower congestion is better
        assert sweep_result.optimal_parameters == {"target_density": 0.6}

    def test_identify_optimal_skips_failed_trials(self) -> None:
        """Test that optimal identification skips failed trials."""
        eco1 = create_eco("buffer_insertion", max_capacitance=0.1)
        eco2 = create_eco("buffer_insertion", max_capacitance=0.2)

        results = [
            ParameterSetResult(
                parameters={"max_capacitance": 0.1},
                eco_instance=eco1,
                metrics={"wns_ps": 500},  # Would be best, but failed
                success=False,  # Failed
            ),
            ParameterSetResult(
                parameters={"max_capacitance": 0.2},
                eco_instance=eco2,
                metrics={"wns_ps": -200},  # Best of successful trials
                success=True,
            ),
        ]

        param_range = ParameterRange(name="max_capacitance", values=[0.1, 0.2])
        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range],
            sweep_mode="sequential",
        )

        sweep_result = analyze_sweep_results(
            sweep_config=config, results=results, metric_name="wns_ps", maximize=True
        )

        # Should pick 0.2, not 0.1 (which failed)
        assert sweep_result.optimal_parameters == {"max_capacitance": 0.2}


class TestSensitivityAnalysis:
    """Tests for parameter sensitivity analysis."""

    def test_compute_sensitivity_analysis(self) -> None:
        """Step 6: Report parameter sensitivity analysis."""
        eco1 = create_eco("buffer_insertion", max_capacitance=0.1)
        eco2 = create_eco("buffer_insertion", max_capacitance=0.2)
        eco3 = create_eco("buffer_insertion", max_capacitance=0.3)

        results = [
            ParameterSetResult(
                parameters={"max_capacitance": 0.1},
                eco_instance=eco1,
                metrics={"wns_ps": -1000},
                success=True,
            ),
            ParameterSetResult(
                parameters={"max_capacitance": 0.2},
                eco_instance=eco2,
                metrics={"wns_ps": -500},
                success=True,
            ),
            ParameterSetResult(
                parameters={"max_capacitance": 0.3},
                eco_instance=eco3,
                metrics={"wns_ps": -200},
                success=True,
            ),
        ]

        param_range = ParameterRange(name="max_capacitance", values=[0.1, 0.2, 0.3])
        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range],
            sweep_mode="sequential",
        )

        sweep_result = analyze_sweep_results(
            sweep_config=config, results=results, metric_name="wns_ps", maximize=True
        )

        # Verify sensitivity analysis was computed
        assert "max_capacitance" in sweep_result.sensitivity_analysis

        sensitivity = sweep_result.sensitivity_analysis["max_capacitance"]
        assert "range" in sensitivity
        assert "average" in sensitivity
        assert "sensitivity" in sensitivity
        assert "num_samples" in sensitivity

        # Range should be 800 (from -1000 to -200)
        assert sensitivity["range"] == 800

        # Average should be -566.67 (approx)
        assert abs(sensitivity["average"] - (-566.67)) < 1

        # Sensitivity should be positive
        assert sensitivity["sensitivity"] > 0

    def test_compute_sensitivity_with_multiple_parameters(self) -> None:
        """Test sensitivity analysis with multiple swept parameters."""
        eco1 = create_eco("buffer_insertion", max_capacitance=0.1, buffer_cell="BUF_X2")
        eco2 = create_eco("buffer_insertion", max_capacitance=0.2, buffer_cell="BUF_X2")
        eco3 = create_eco("buffer_insertion", max_capacitance=0.1, buffer_cell="BUF_X4")

        results = [
            ParameterSetResult(
                parameters={"max_capacitance": 0.1, "buffer_cell": "BUF_X2"},
                eco_instance=eco1,
                metrics={"wns_ps": -1000},
                success=True,
            ),
            ParameterSetResult(
                parameters={"max_capacitance": 0.2, "buffer_cell": "BUF_X2"},
                eco_instance=eco2,
                metrics={"wns_ps": -500},
                success=True,
            ),
            ParameterSetResult(
                parameters={"max_capacitance": 0.1, "buffer_cell": "BUF_X4"},
                eco_instance=eco3,
                metrics={"wns_ps": -800},
                success=True,
            ),
        ]

        param_range1 = ParameterRange(name="max_capacitance", values=[0.1, 0.2])
        param_range2 = ParameterRange(name="buffer_cell", values=["BUF_X2", "BUF_X4"])

        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range1, param_range2],
            sweep_mode="sequential",
        )

        sweep_result = analyze_sweep_results(
            sweep_config=config, results=results, metric_name="wns_ps", maximize=True
        )

        # Both parameters should have sensitivity data
        assert "max_capacitance" in sweep_result.sensitivity_analysis
        assert "buffer_cell" in sweep_result.sensitivity_analysis


class TestParameterSweepResult:
    """Tests for ParameterSweepResult dataclass."""

    def test_parameter_sweep_result_to_dict(self) -> None:
        """Test converting sweep result to dictionary."""
        param_range = ParameterRange(name="max_capacitance", values=[0.1, 0.2])
        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range],
            sweep_mode="sequential",
        )

        eco1 = create_eco("buffer_insertion", max_capacitance=0.1)
        eco2 = create_eco("buffer_insertion", max_capacitance=0.2)

        results = [
            ParameterSetResult(
                parameters={"max_capacitance": 0.1},
                eco_instance=eco1,
                metrics={"wns_ps": -500},
                success=True,
            ),
            ParameterSetResult(
                parameters={"max_capacitance": 0.2},
                eco_instance=eco2,
                metrics={"wns_ps": -200},
                success=True,
            ),
        ]

        sweep_result = ParameterSweepResult(
            eco_name="buffer_insertion",
            sweep_config=config,
            results=results,
            optimal_parameters={"max_capacitance": 0.2},
        )

        result_dict = sweep_result.to_dict()

        assert result_dict["eco_name"] == "buffer_insertion"
        assert result_dict["sweep_mode"] == "sequential"
        assert result_dict["total_trials"] == 2
        assert result_dict["successful_trials"] == 2
        assert result_dict["optimal_parameters"] == {"max_capacitance": 0.2}
        assert len(result_dict["results"]) == 2


class TestEndToEndParameterSweep:
    """End-to-end tests for parameter sweep workflow."""

    def test_complete_parameter_sweep_workflow(self) -> None:
        """Test complete parameter sweep workflow from config to analysis."""
        # Step 1 & 2: Define ECO with tunable parameter and configure sweep
        param_range = ParameterRange(
            name="max_capacitance", values=[0.1, 0.15, 0.2, 0.25, 0.3]
        )

        config = ParameterSweepConfig(
            eco_name="buffer_insertion",
            parameter_ranges=[param_range],
            fixed_parameters={"buffer_cell": "BUF_X4"},
            sweep_mode="sequential",
        )

        # Step 3: Generate trials
        ecos = create_sweep_ecos(config)
        assert len(ecos) == 5

        # Step 4: Simulate execution (in real use, these would be trial runs)
        results = []
        simulated_wns = [-800, -600, -300, -400, -500]  # 0.2 is best

        for i, eco in enumerate(ecos):
            result = ParameterSetResult(
                parameters=eco.metadata.parameters,
                eco_instance=eco,
                metrics={"wns_ps": simulated_wns[i]},
                success=True,
            )
            results.append(result)

        # Step 5 & 6: Analyze results and identify optimal parameters
        sweep_analysis = analyze_sweep_results(
            sweep_config=config, results=results, metric_name="wns_ps", maximize=True
        )

        # Verify optimal parameters identified (0.2 has WNS of -300, best)
        assert sweep_analysis.optimal_parameters == {
            "max_capacitance": 0.2,
            "buffer_cell": "BUF_X4",
        }

        # Verify sensitivity analysis computed
        assert "max_capacitance" in sweep_analysis.sensitivity_analysis

        # Verify serialization works
        result_dict = sweep_analysis.to_dict()
        assert result_dict["total_trials"] == 5
        assert result_dict["successful_trials"] == 5
