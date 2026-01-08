"""Custom metric extractor framework for project-specific KPIs.

This module enables users to define and register custom metric extractors
that can parse trial artifacts and extract project-specific metrics beyond
the standard timing and congestion metrics.

Example usage:
    # Define a custom extractor
    class PowerMetricExtractor(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, Any]:
            power_report = artifact_dir / "power.rpt"
            if not power_report.exists():
                return {}

            # Parse power report
            total_power = self._parse_power_report(power_report)
            return {"total_power_mw": total_power}

    # Register the extractor
    registry = MetricExtractorRegistry()
    registry.register("power", PowerMetricExtractor())

    # Use in trial execution
    metrics = registry.extract_all(trial_artifact_dir)
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class MetricExtractor(ABC):
    """Base class for custom metric extractors.

    Subclasses must implement the extract() method to parse trial artifacts
    and return a dictionary of custom metrics.
    """

    @abstractmethod
    def extract(self, artifact_dir: Path) -> dict[str, Any]:
        """Extract custom metrics from trial artifacts.

        Args:
            artifact_dir: Path to trial artifact directory containing reports,
                         logs, and other output files

        Returns:
            Dictionary mapping metric names to values. Keys should be valid
            Python identifiers using lowercase_with_underscores convention.
            Values can be numbers, strings, or simple data structures (lists, dicts).

        Raises:
            May raise exceptions if critical parsing errors occur, but should
            gracefully return empty dict {} for missing or optional artifacts.
        """
        pass

    def validate_metrics(self, metrics: dict[str, Any]) -> bool:
        """Validate extracted metrics.

        Override this method to add custom validation logic.

        Args:
            metrics: Dictionary of extracted metrics

        Returns:
            True if metrics are valid, False otherwise
        """
        # Default validation: check keys are strings and values are JSON-serializable
        if not isinstance(metrics, dict):
            return False

        for key, value in metrics.items():
            if not isinstance(key, str):
                return False

            # Check if value is JSON-serializable basic types
            if not isinstance(value, (int, float, str, bool, list, dict, type(None))):
                return False

        return True


class MetricExtractorRegistry:
    """Registry for managing custom metric extractors.

    This registry allows multiple extractors to be registered and executed
    in order during trial execution.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._extractors: dict[str, MetricExtractor] = {}
        self._execution_order: list[str] = []

    def register(self, name: str, extractor: MetricExtractor) -> None:
        """Register a custom metric extractor.

        Args:
            name: Unique identifier for the extractor (e.g., "power", "area")
            extractor: MetricExtractor instance

        Raises:
            ValueError: If name is already registered
        """
        if name in self._extractors:
            raise ValueError(f"Extractor '{name}' is already registered")

        if not isinstance(extractor, MetricExtractor):
            raise TypeError(f"Extractor must be instance of MetricExtractor, got {type(extractor)}")

        self._extractors[name] = extractor
        self._execution_order.append(name)

    def unregister(self, name: str) -> None:
        """Unregister a custom metric extractor.

        Args:
            name: Identifier of extractor to remove

        Raises:
            KeyError: If name is not registered
        """
        if name not in self._extractors:
            raise KeyError(f"Extractor '{name}' is not registered")

        del self._extractors[name]
        self._execution_order.remove(name)

    def get(self, name: str) -> MetricExtractor:
        """Get a registered extractor by name.

        Args:
            name: Identifier of extractor

        Returns:
            MetricExtractor instance

        Raises:
            KeyError: If name is not registered
        """
        if name not in self._extractors:
            raise KeyError(f"Extractor '{name}' is not registered")
        return self._extractors[name]

    def list_extractors(self) -> list[str]:
        """List all registered extractor names in execution order.

        Returns:
            List of extractor names
        """
        return self._execution_order.copy()

    def extract_all(self, artifact_dir: Path) -> dict[str, dict[str, Any]]:
        """Execute all registered extractors on trial artifacts.

        Args:
            artifact_dir: Path to trial artifact directory

        Returns:
            Dictionary mapping extractor names to their extracted metrics:
            {
                "power": {"total_power_mw": 125.3, "leakage_power_mw": 12.1},
                "area": {"total_area_um2": 50000.0},
                ...
            }
        """
        results: dict[str, dict[str, Any]] = {}

        for name in self._execution_order:
            extractor = self._extractors[name]
            try:
                metrics = extractor.extract(artifact_dir)

                # Validate metrics
                if not extractor.validate_metrics(metrics):
                    # Log warning but continue
                    results[name] = {"_error": "Invalid metrics format"}
                    continue

                results[name] = metrics
            except Exception as e:
                # Capture errors without failing entire extraction
                results[name] = {"_error": str(e)}

        return results

    def extract_flat(self, artifact_dir: Path, prefix_with_extractor: bool = False) -> dict[str, Any]:
        """Execute all extractors and return flattened metrics dictionary.

        Args:
            artifact_dir: Path to trial artifact directory
            prefix_with_extractor: If True, prefix metric keys with extractor name
                                  (e.g., "power_total_power_mw"). If False, merge
                                  all metrics into single flat dict (keys may collide).

        Returns:
            Flattened dictionary of all metrics
        """
        nested_results = self.extract_all(artifact_dir)
        flat_results: dict[str, Any] = {}

        for extractor_name, metrics in nested_results.items():
            for key, value in metrics.items():
                if prefix_with_extractor:
                    flat_key = f"{extractor_name}_{key}"
                else:
                    flat_key = key

                # Handle key collisions
                if flat_key in flat_results:
                    # If collision, use prefixed version
                    flat_key = f"{extractor_name}_{key}"

                flat_results[flat_key] = value

        return flat_results


# Example built-in custom extractors

class CellCountExtractor(MetricExtractor):
    """Extract cell count and instance statistics from OpenROAD reports."""

    def extract(self, artifact_dir: Path) -> dict[str, Any]:
        """Extract cell count metrics.

        Looks for OpenROAD report_design_area or similar reports.
        """
        # Look for common report files
        report_files = [
            artifact_dir / "report_design_area.txt",
            artifact_dir / "design_area.rpt",
            artifact_dir / "metrics.txt",
        ]

        metrics: dict[str, Any] = {}

        for report_path in report_files:
            if report_path.exists():
                content = report_path.read_text()
                metrics.update(self._parse_cell_counts(content))

        return metrics

    def _parse_cell_counts(self, content: str) -> dict[str, Any]:
        """Parse cell count from report content."""
        import re

        result = {}

        # Match patterns like:
        # "Number of cells: 1234"
        # "Instance count: 5678"
        # "Total instances: 910"
        cell_match = re.search(r"(?:cells?|instances?)\s*:\s*(\d+)", content, re.IGNORECASE)
        if cell_match:
            result["cell_count"] = int(cell_match.group(1))

        # Match patterns like "combinational cells: 123"
        comb_match = re.search(r"combinational\s+(?:cells?|instances?)\s*:\s*(\d+)", content, re.IGNORECASE)
        if comb_match:
            result["combinational_cells"] = int(comb_match.group(1))

        # Match patterns like "sequential cells: 456"
        seq_match = re.search(r"sequential\s+(?:cells?|instances?)\s*:\s*(\d+)", content, re.IGNORECASE)
        if seq_match:
            result["sequential_cells"] = int(seq_match.group(1))

        return result


class WirelengthExtractor(MetricExtractor):
    """Extract wirelength metrics from OpenROAD reports."""

    def extract(self, artifact_dir: Path) -> dict[str, Any]:
        """Extract wirelength metrics."""
        # Look for wirelength reports
        report_files = [
            artifact_dir / "route.log",
            artifact_dir / "global_route.rpt",
            artifact_dir / "metrics.txt",
        ]

        metrics: dict[str, Any] = {}

        for report_path in report_files:
            if report_path.exists():
                content = report_path.read_text()
                metrics.update(self._parse_wirelength(content))

        return metrics

    def _parse_wirelength(self, content: str) -> dict[str, Any]:
        """Parse wirelength from report content."""
        import re

        result = {}

        # Match patterns like:
        # "Total wirelength: 12345 um"
        # "Wire length: 67890.5"
        wl_match = re.search(r"(?:total\s+)?wire\s*length\s*:\s*(\d+\.?\d*)\s*(um|µm|microns?)?",
                           content, re.IGNORECASE)
        if wl_match:
            value = float(wl_match.group(1))
            unit = wl_match.group(2)

            # Convert to micrometers
            if unit and "micron" in unit.lower():
                result["total_wirelength_um"] = value
            else:
                # Assume um if no unit
                result["total_wirelength_um"] = value

        return result


def create_default_registry() -> MetricExtractorRegistry:
    """Create a registry with built-in example extractors.

    Returns:
        MetricExtractorRegistry with cell count and wirelength extractors registered
    """
    registry = MetricExtractorRegistry()
    registry.register("cell_count", CellCountExtractor())
    registry.register("wirelength", WirelengthExtractor())
    return registry
