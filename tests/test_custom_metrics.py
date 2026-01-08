"""Tests for custom metric extractor framework."""

import tempfile
from pathlib import Path

import pytest

from src.parsers.custom_metrics import (
    CellCountExtractor,
    MetricExtractor,
    MetricExtractorRegistry,
    WirelengthExtractor,
    create_default_registry,
)


# Test MetricExtractor base class


class SimpleMetricExtractor(MetricExtractor):
    """Simple extractor for testing."""

    def extract(self, artifact_dir: Path) -> dict[str, any]:
        return {"test_metric": 42}


class ErrorMetricExtractor(MetricExtractor):
    """Extractor that raises errors."""

    def extract(self, artifact_dir: Path) -> dict[str, any]:
        raise ValueError("Simulated extraction error")


def test_metric_extractor_is_abstract():
    """Test that MetricExtractor cannot be instantiated directly."""
    with pytest.raises(TypeError):
        MetricExtractor()  # type: ignore


def test_simple_extractor_can_be_instantiated():
    """Test that concrete extractor can be created."""
    extractor = SimpleMetricExtractor()
    assert extractor is not None


def test_simple_extractor_extract():
    """Test that simple extractor returns expected metrics."""
    extractor = SimpleMetricExtractor()
    metrics = extractor.extract(Path("/tmp"))
    assert metrics == {"test_metric": 42}


def test_metric_extractor_validate_valid_metrics():
    """Test that validation accepts valid metrics."""
    extractor = SimpleMetricExtractor()
    valid_metrics = {
        "int_metric": 10,
        "float_metric": 3.14,
        "str_metric": "value",
        "bool_metric": True,
        "list_metric": [1, 2, 3],
        "dict_metric": {"nested": "value"},
        "none_metric": None,
    }
    assert extractor.validate_metrics(valid_metrics) is True


def test_metric_extractor_validate_invalid_type():
    """Test that validation rejects non-dict metrics."""
    extractor = SimpleMetricExtractor()
    assert extractor.validate_metrics("not a dict") is False  # type: ignore
    assert extractor.validate_metrics([1, 2, 3]) is False  # type: ignore


def test_metric_extractor_validate_invalid_keys():
    """Test that validation rejects non-string keys."""
    extractor = SimpleMetricExtractor()
    invalid_metrics = {123: "value"}  # type: ignore
    assert extractor.validate_metrics(invalid_metrics) is False


def test_metric_extractor_validate_invalid_values():
    """Test that validation rejects non-JSON-serializable values."""
    extractor = SimpleMetricExtractor()
    invalid_metrics = {"key": object()}  # object is not JSON-serializable
    assert extractor.validate_metrics(invalid_metrics) is False


# Test MetricExtractorRegistry


def test_registry_initialization():
    """Test that registry can be created."""
    registry = MetricExtractorRegistry()
    assert registry is not None
    assert registry.list_extractors() == []


def test_registry_register_extractor():
    """Test registering an extractor."""
    registry = MetricExtractorRegistry()
    extractor = SimpleMetricExtractor()

    registry.register("test", extractor)
    assert "test" in registry.list_extractors()


def test_registry_register_duplicate_name():
    """Test that registering duplicate name raises error."""
    registry = MetricExtractorRegistry()
    extractor1 = SimpleMetricExtractor()
    extractor2 = SimpleMetricExtractor()

    registry.register("test", extractor1)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("test", extractor2)


def test_registry_register_invalid_type():
    """Test that registering non-extractor raises error."""
    registry = MetricExtractorRegistry()

    with pytest.raises(TypeError, match="must be instance of MetricExtractor"):
        registry.register("invalid", "not an extractor")  # type: ignore


def test_registry_unregister_extractor():
    """Test unregistering an extractor."""
    registry = MetricExtractorRegistry()
    extractor = SimpleMetricExtractor()

    registry.register("test", extractor)
    assert "test" in registry.list_extractors()

    registry.unregister("test")
    assert "test" not in registry.list_extractors()


def test_registry_unregister_nonexistent():
    """Test that unregistering nonexistent name raises error."""
    registry = MetricExtractorRegistry()

    with pytest.raises(KeyError, match="not registered"):
        registry.unregister("nonexistent")


def test_registry_get_extractor():
    """Test retrieving a registered extractor."""
    registry = MetricExtractorRegistry()
    extractor = SimpleMetricExtractor()

    registry.register("test", extractor)
    retrieved = registry.get("test")
    assert retrieved is extractor


def test_registry_get_nonexistent():
    """Test that getting nonexistent extractor raises error."""
    registry = MetricExtractorRegistry()

    with pytest.raises(KeyError, match="not registered"):
        registry.get("nonexistent")


def test_registry_list_extractors_order():
    """Test that extractors are listed in registration order."""
    registry = MetricExtractorRegistry()
    ext1 = SimpleMetricExtractor()
    ext2 = SimpleMetricExtractor()
    ext3 = SimpleMetricExtractor()

    registry.register("first", ext1)
    registry.register("second", ext2)
    registry.register("third", ext3)

    assert registry.list_extractors() == ["first", "second", "third"]


def test_registry_extract_all_single_extractor():
    """Test extracting metrics with single extractor."""
    registry = MetricExtractorRegistry()
    extractor = SimpleMetricExtractor()
    registry.register("test", extractor)

    with tempfile.TemporaryDirectory() as tmpdir:
        results = registry.extract_all(Path(tmpdir))

    assert "test" in results
    assert results["test"] == {"test_metric": 42}


def test_registry_extract_all_multiple_extractors():
    """Test extracting metrics with multiple extractors."""
    class Extractor1(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {"metric1": 10}

    class Extractor2(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {"metric2": 20}

    registry = MetricExtractorRegistry()
    registry.register("ext1", Extractor1())
    registry.register("ext2", Extractor2())

    with tempfile.TemporaryDirectory() as tmpdir:
        results = registry.extract_all(Path(tmpdir))

    assert "ext1" in results
    assert "ext2" in results
    assert results["ext1"] == {"metric1": 10}
    assert results["ext2"] == {"metric2": 20}


def test_registry_extract_all_handles_errors():
    """Test that registry handles extractor errors gracefully."""
    registry = MetricExtractorRegistry()
    registry.register("error", ErrorMetricExtractor())
    registry.register("success", SimpleMetricExtractor())

    with tempfile.TemporaryDirectory() as tmpdir:
        results = registry.extract_all(Path(tmpdir))

    # Error extractor should have error in results
    assert "error" in results
    assert "_error" in results["error"]
    assert "Simulated extraction error" in results["error"]["_error"]

    # Success extractor should work fine
    assert "success" in results
    assert results["success"] == {"test_metric": 42}


def test_registry_extract_all_validates_metrics():
    """Test that invalid metrics are caught during extraction."""
    class InvalidMetricsExtractor(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {123: "invalid key"}  # type: ignore

    registry = MetricExtractorRegistry()
    registry.register("invalid", InvalidMetricsExtractor())

    with tempfile.TemporaryDirectory() as tmpdir:
        results = registry.extract_all(Path(tmpdir))

    assert "invalid" in results
    assert "_error" in results["invalid"]
    assert "Invalid metrics format" in results["invalid"]["_error"]


def test_registry_extract_flat_without_prefix():
    """Test flattened extraction without prefixes."""
    class Extractor1(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {"metric_a": 10, "metric_b": 20}

    class Extractor2(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {"metric_c": 30}

    registry = MetricExtractorRegistry()
    registry.register("ext1", Extractor1())
    registry.register("ext2", Extractor2())

    with tempfile.TemporaryDirectory() as tmpdir:
        results = registry.extract_flat(Path(tmpdir), prefix_with_extractor=False)

    assert results == {
        "metric_a": 10,
        "metric_b": 20,
        "metric_c": 30,
    }


def test_registry_extract_flat_with_prefix():
    """Test flattened extraction with prefixes."""
    class Extractor1(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {"metric": 10}

    class Extractor2(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {"metric": 20}

    registry = MetricExtractorRegistry()
    registry.register("ext1", Extractor1())
    registry.register("ext2", Extractor2())

    with tempfile.TemporaryDirectory() as tmpdir:
        results = registry.extract_flat(Path(tmpdir), prefix_with_extractor=True)

    assert results == {
        "ext1_metric": 10,
        "ext2_metric": 20,
    }


def test_registry_extract_flat_handles_collisions():
    """Test that flat extraction handles key collisions."""
    class Extractor1(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {"conflict": 10}

    class Extractor2(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {"conflict": 20}

    registry = MetricExtractorRegistry()
    registry.register("ext1", Extractor1())
    registry.register("ext2", Extractor2())

    with tempfile.TemporaryDirectory() as tmpdir:
        results = registry.extract_flat(Path(tmpdir), prefix_with_extractor=False)

    # Should resolve collision by prefixing the second occurrence
    assert "conflict" in results or "ext1_conflict" in results
    assert "ext2_conflict" in results


# Test built-in extractors


def test_cell_count_extractor_instantiation():
    """Test that CellCountExtractor can be created."""
    extractor = CellCountExtractor()
    assert extractor is not None


def test_cell_count_extractor_empty_directory():
    """Test CellCountExtractor on empty directory."""
    extractor = CellCountExtractor()

    with tempfile.TemporaryDirectory() as tmpdir:
        metrics = extractor.extract(Path(tmpdir))

    assert metrics == {}


def test_cell_count_extractor_with_report():
    """Test CellCountExtractor with valid report."""
    extractor = CellCountExtractor()

    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "metrics.txt"
        report_path.write_text("""
Design Statistics:
Number of cells: 1234
Combinational cells: 800
Sequential cells: 434
        """)

        metrics = extractor.extract(Path(tmpdir))

    assert "cell_count" in metrics
    assert metrics["cell_count"] == 1234
    assert metrics["combinational_cells"] == 800
    assert metrics["sequential_cells"] == 434


def test_cell_count_extractor_various_formats():
    """Test CellCountExtractor with different report formats."""
    extractor = CellCountExtractor()

    # Test "instances" instead of "cells"
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "metrics.txt"
        report_path.write_text("Total instances: 5678")

        metrics = extractor.extract(Path(tmpdir))

    assert metrics["cell_count"] == 5678


def test_wirelength_extractor_instantiation():
    """Test that WirelengthExtractor can be created."""
    extractor = WirelengthExtractor()
    assert extractor is not None


def test_wirelength_extractor_empty_directory():
    """Test WirelengthExtractor on empty directory."""
    extractor = WirelengthExtractor()

    with tempfile.TemporaryDirectory() as tmpdir:
        metrics = extractor.extract(Path(tmpdir))

    assert metrics == {}


def test_wirelength_extractor_with_report():
    """Test WirelengthExtractor with valid report."""
    extractor = WirelengthExtractor()

    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "metrics.txt"
        report_path.write_text("""
Routing Statistics:
Total wirelength: 123456.78 um
        """)

        metrics = extractor.extract(Path(tmpdir))

    assert "total_wirelength_um" in metrics
    assert metrics["total_wirelength_um"] == 123456.78


def test_wirelength_extractor_various_formats():
    """Test WirelengthExtractor with different formats."""
    extractor = WirelengthExtractor()

    # Test without unit
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "metrics.txt"
        report_path.write_text("Wire length: 987654.32")

        metrics = extractor.extract(Path(tmpdir))

    assert metrics["total_wirelength_um"] == 987654.32


# Test default registry


def test_create_default_registry():
    """Test that default registry is created with built-in extractors."""
    registry = create_default_registry()

    extractors = registry.list_extractors()
    assert "cell_count" in extractors
    assert "wirelength" in extractors


def test_default_registry_extractors_work():
    """Test that default registry extractors can execute."""
    registry = create_default_registry()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create sample reports
        (Path(tmpdir) / "metrics.txt").write_text("""
Number of cells: 2000
Total wirelength: 50000.0 um
        """)

        results = registry.extract_all(Path(tmpdir))

    assert "cell_count" in results
    assert "wirelength" in results
    assert results["cell_count"]["cell_count"] == 2000
    assert results["wirelength"]["total_wirelength_um"] == 50000.0


# Integration tests


def test_end_to_end_custom_extractor_workflow():
    """Test complete workflow: define, register, extract."""
    # Define custom extractor
    class PowerExtractor(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            power_report = artifact_dir / "power.rpt"
            if not power_report.exists():
                return {}

            content = power_report.read_text()
            # Simple parsing
            import re
            match = re.search(r"Total Power:\s*(\d+\.?\d*)\s*mW", content)
            if match:
                return {"total_power_mw": float(match.group(1))}
            return {}

    # Register extractor
    registry = MetricExtractorRegistry()
    registry.register("power", PowerExtractor())

    # Create artifacts
    with tempfile.TemporaryDirectory() as tmpdir:
        power_report = Path(tmpdir) / "power.rpt"
        power_report.write_text("Total Power: 125.3 mW")

        # Extract metrics
        metrics = registry.extract_all(Path(tmpdir))

    # Verify
    assert "power" in metrics
    assert metrics["power"]["total_power_mw"] == 125.3


def test_custom_extractor_with_validation_override():
    """Test custom extractor with overridden validation."""
    class StrictExtractor(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {"value": 100}

        def validate_metrics(self, metrics: dict[str, any]) -> bool:
            # Require "value" key to be present and positive
            if "value" not in metrics:
                return False
            if not isinstance(metrics["value"], (int, float)):
                return False
            return metrics["value"] > 0

    extractor = StrictExtractor()

    # Valid metrics
    assert extractor.validate_metrics({"value": 100}) is True

    # Invalid metrics
    assert extractor.validate_metrics({"value": -10}) is False
    assert extractor.validate_metrics({"other": 100}) is False


def test_registry_with_mixed_success_and_failure():
    """Test registry with mix of successful and failing extractors."""
    class SuccessExtractor(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {"success_metric": 123}

    class FailExtractor(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            raise RuntimeError("Extraction failed")

    class EmptyExtractor(MetricExtractor):
        def extract(self, artifact_dir: Path) -> dict[str, any]:
            return {}

    registry = MetricExtractorRegistry()
    registry.register("success", SuccessExtractor())
    registry.register("fail", FailExtractor())
    registry.register("empty", EmptyExtractor())

    with tempfile.TemporaryDirectory() as tmpdir:
        results = registry.extract_all(Path(tmpdir))

    # Success extractor should work
    assert results["success"] == {"success_metric": 123}

    # Fail extractor should have error
    assert "_error" in results["fail"]

    # Empty extractor should return empty dict
    assert results["empty"] == {}
