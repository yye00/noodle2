"""ECO parameter sweep support for systematic variation and sensitivity analysis.

This module enables:
- Systematic variation of ECO parameters across trials
- Parameter sensitivity analysis
- Optimal parameter value identification
- Reproducible parameter space exploration
"""

from dataclasses import dataclass, field
from typing import Any

from .eco import ECO, create_eco


@dataclass
class ParameterRange:
    """Defines a range of values for parameter sweeping.

    Attributes:
        name: Parameter name
        values: List of values to sweep
        type: Parameter type hint (for validation)
    """

    name: str
    values: list[Any]
    type: str = "auto"  # auto, int, float, str, bool

    def __post_init__(self) -> None:
        """Validate parameter range."""
        if not self.name:
            raise ValueError("Parameter name cannot be empty")
        if not self.values:
            raise ValueError("Parameter values list cannot be empty")
        if len(self.values) != len(set(str(v) for v in self.values)):
            raise ValueError(f"Parameter values must be unique: {self.values}")


@dataclass
class ParameterSweepConfig:
    """Configuration for ECO parameter sweep.

    Attributes:
        eco_name: Base ECO name to sweep
        parameter_ranges: List of parameters to sweep
        fixed_parameters: Parameters that remain constant across all trials
        sweep_mode: How to combine parameters ("grid", "sequential")
    """

    eco_name: str
    parameter_ranges: list[ParameterRange]
    fixed_parameters: dict[str, Any] = field(default_factory=dict)
    sweep_mode: str = "sequential"  # "sequential" or "grid"

    def __post_init__(self) -> None:
        """Validate sweep configuration."""
        if not self.eco_name:
            raise ValueError("ECO name cannot be empty")
        if not self.parameter_ranges:
            raise ValueError("Must specify at least one parameter range")
        if self.sweep_mode not in ["sequential", "grid"]:
            raise ValueError(f"Invalid sweep_mode: {self.sweep_mode}")

        # Ensure no overlap between parameter_ranges and fixed_parameters
        swept_params = {pr.name for pr in self.parameter_ranges}
        fixed_params = set(self.fixed_parameters.keys())
        overlap = swept_params & fixed_params
        if overlap:
            raise ValueError(
                f"Parameters cannot be both swept and fixed: {overlap}"
            )


@dataclass
class ParameterSetResult:
    """Result of executing one parameter set in a sweep.

    Attributes:
        parameters: The parameter values used
        eco_instance: The ECO instance that was executed
        metrics: Metrics from trial execution (WNS, TNS, etc.)
        success: Whether the trial succeeded
    """

    parameters: dict[str, Any]
    eco_instance: ECO
    metrics: dict[str, float] = field(default_factory=dict)
    success: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "parameters": self.parameters,
            "eco_name": self.eco_instance.name,
            "metrics": self.metrics,
            "success": self.success,
        }


@dataclass
class ParameterSweepResult:
    """Complete results of a parameter sweep.

    Attributes:
        eco_name: ECO that was swept
        sweep_config: Original sweep configuration
        results: Results for each parameter set
        optimal_parameters: Best parameter set based on primary metric
        sensitivity_analysis: Parameter sensitivity metrics
    """

    eco_name: str
    sweep_config: ParameterSweepConfig
    results: list[ParameterSetResult] = field(default_factory=list)
    optimal_parameters: dict[str, Any] | None = None
    sensitivity_analysis: dict[str, dict[str, float]] = field(default_factory=dict)

    def identify_optimal(self, metric_name: str = "wns_ps", maximize: bool = True) -> None:
        """Identify optimal parameter set based on specified metric.

        Args:
            metric_name: Metric to optimize (e.g., "wns_ps", "congestion")
            maximize: If True, maximize metric; if False, minimize
        """
        if not self.results:
            return

        # Filter successful results
        successful_results = [r for r in self.results if r.success]
        if not successful_results:
            return

        # Find best result
        best_result = None
        best_value = None

        for result in successful_results:
            if metric_name not in result.metrics:
                continue

            value = result.metrics[metric_name]
            if best_value is None:
                best_result = result
                best_value = value
            elif maximize and value > best_value:
                best_result = result
                best_value = value
            elif not maximize and value < best_value:
                best_result = result
                best_value = value

        if best_result:
            self.optimal_parameters = best_result.parameters.copy()

    def compute_sensitivity(self, metric_name: str = "wns_ps") -> None:
        """Compute parameter sensitivity analysis.

        Calculates how much each parameter affects the target metric.

        Args:
            metric_name: Metric to analyze
        """
        if not self.results:
            return

        # Group results by parameter
        param_impacts: dict[str, list[tuple[Any, float]]] = {}

        for result in self.results:
            if not result.success or metric_name not in result.metrics:
                continue

            metric_value = result.metrics[metric_name]

            for param_name, param_value in result.parameters.items():
                if param_name not in param_impacts:
                    param_impacts[param_name] = []
                param_impacts[param_name].append((param_value, metric_value))

        # Calculate sensitivity for each parameter
        self.sensitivity_analysis = {}

        for param_name, values_and_metrics in param_impacts.items():
            if len(values_and_metrics) < 2:
                continue

            # Calculate range of metric values
            metric_values = [m for _, m in values_and_metrics]
            metric_range = max(metric_values) - min(metric_values)

            # Calculate average metric value
            avg_metric = sum(metric_values) / len(metric_values)

            # Sensitivity = range / avg (normalized)
            sensitivity = metric_range / avg_metric if avg_metric != 0 else 0

            self.sensitivity_analysis[param_name] = {
                "range": metric_range,
                "average": avg_metric,
                "sensitivity": abs(sensitivity),
                "num_samples": len(values_and_metrics),
            }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "eco_name": self.eco_name,
            "sweep_mode": self.sweep_config.sweep_mode,
            "results": [r.to_dict() for r in self.results],
            "optimal_parameters": self.optimal_parameters,
            "sensitivity_analysis": self.sensitivity_analysis,
            "total_trials": len(self.results),
            "successful_trials": sum(1 for r in self.results if r.success),
        }


def generate_parameter_sets(config: ParameterSweepConfig) -> list[dict[str, Any]]:
    """Generate all parameter combinations for a sweep.

    Args:
        config: Parameter sweep configuration

    Returns:
        List of parameter dictionaries, one per trial
    """
    if config.sweep_mode == "sequential":
        return _generate_sequential_sweep(config)
    elif config.sweep_mode == "grid":
        return _generate_grid_sweep(config)
    else:
        raise ValueError(f"Unknown sweep_mode: {config.sweep_mode}")


def _generate_sequential_sweep(config: ParameterSweepConfig) -> list[dict[str, Any]]:
    """Generate parameter sets for sequential sweep (one parameter at a time).

    Args:
        config: Parameter sweep configuration

    Returns:
        List of parameter dictionaries
    """
    parameter_sets = []

    # For sequential sweep, vary one parameter at a time
    # All other parameters use their first value
    for param_range in config.parameter_ranges:
        for value in param_range.values:
            param_set = config.fixed_parameters.copy()

            # Set baseline values for all swept parameters
            for pr in config.parameter_ranges:
                if pr.name != param_range.name:
                    param_set[pr.name] = pr.values[0]  # Use first value as baseline

            # Set the varying parameter
            param_set[param_range.name] = value

            parameter_sets.append(param_set)

    return parameter_sets


def _generate_grid_sweep(config: ParameterSweepConfig) -> list[dict[str, Any]]:
    """Generate parameter sets for grid sweep (all combinations).

    Args:
        config: Parameter sweep configuration

    Returns:
        List of parameter dictionaries
    """
    import itertools

    # Generate Cartesian product of all parameter values
    param_names = [pr.name for pr in config.parameter_ranges]
    param_value_lists = [pr.values for pr in config.parameter_ranges]

    parameter_sets = []
    for value_combination in itertools.product(*param_value_lists):
        param_set = config.fixed_parameters.copy()
        for name, value in zip(param_names, value_combination):
            param_set[name] = value
        parameter_sets.append(param_set)

    return parameter_sets


def create_sweep_ecos(config: ParameterSweepConfig) -> list[ECO]:
    """Create ECO instances for all parameter combinations in a sweep.

    Args:
        config: Parameter sweep configuration

    Returns:
        List of ECO instances, one per parameter set

    Raises:
        ValueError: If ECO creation fails
    """
    parameter_sets = generate_parameter_sets(config)

    ecos = []
    for param_set in parameter_sets:
        eco = create_eco(config.eco_name, **param_set)
        ecos.append(eco)

    return ecos


def analyze_sweep_results(
    sweep_config: ParameterSweepConfig,
    results: list[ParameterSetResult],
    metric_name: str = "wns_ps",
    maximize: bool = True,
) -> ParameterSweepResult:
    """Analyze parameter sweep results and identify optimal parameters.

    Args:
        sweep_config: Original sweep configuration
        results: Results from all parameter sets
        metric_name: Metric to optimize
        maximize: Whether to maximize (True) or minimize (False) the metric

    Returns:
        Complete sweep analysis with optimal parameters and sensitivity
    """
    sweep_result = ParameterSweepResult(
        eco_name=sweep_config.eco_name,
        sweep_config=sweep_config,
        results=results,
    )

    # Identify optimal parameters
    sweep_result.identify_optimal(metric_name=metric_name, maximize=maximize)

    # Compute sensitivity analysis
    sweep_result.compute_sensitivity(metric_name=metric_name)

    return sweep_result
