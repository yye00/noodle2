"""Tests for ECO blacklist and whitelist filtering."""

import pytest
from pathlib import Path
import tempfile
import yaml

from src.controller.types import (
    ExecutionMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
    ECOClass,
)
from src.controller.study import load_study_config


class TestECOBlacklist:
    """Test ECO blacklist functionality."""

    def test_study_config_has_eco_blacklist_field(self) -> None:
        """StudyConfig should have an eco_blacklist field."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_blacklist=["bad_eco", "broken_eco"],
        )

        assert hasattr(config, "eco_blacklist")
        assert config.eco_blacklist == ["bad_eco", "broken_eco"]

    def test_eco_blacklist_defaults_to_empty_list(self) -> None:
        """ECO blacklist should default to empty list."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
        )

        assert config.eco_blacklist == []

    def test_is_eco_allowed_rejects_blacklisted_eco(self) -> None:
        """is_eco_allowed should reject blacklisted ECOs."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_blacklist=["catastrophic_eco"],
        )

        allowed, reason = config.is_eco_allowed("catastrophic_eco")
        assert not allowed
        assert "blacklisted" in reason.lower()
        assert "catastrophic_eco" in reason

    def test_is_eco_allowed_accepts_non_blacklisted_eco(self) -> None:
        """is_eco_allowed should accept ECOs not in blacklist."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_blacklist=["bad_eco"],
        )

        allowed, reason = config.is_eco_allowed("good_eco")
        assert allowed
        assert reason is None

    def test_blacklist_with_multiple_ecos(self) -> None:
        """Blacklist should support multiple ECOs."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_blacklist=["eco1", "eco2", "eco3"],
        )

        # All blacklisted ECOs should be rejected
        for eco_name in ["eco1", "eco2", "eco3"]:
            allowed, reason = config.is_eco_allowed(eco_name)
            assert not allowed
            assert eco_name in reason

        # Non-blacklisted ECO should be allowed
        allowed, reason = config.is_eco_allowed("eco4")
        assert allowed


class TestECOWhitelist:
    """Test ECO whitelist functionality."""

    def test_study_config_has_eco_whitelist_field(self) -> None:
        """StudyConfig should have an eco_whitelist field."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_whitelist=["approved_eco1", "approved_eco2"],
        )

        assert hasattr(config, "eco_whitelist")
        assert config.eco_whitelist == ["approved_eco1", "approved_eco2"]

    def test_eco_whitelist_defaults_to_none(self) -> None:
        """ECO whitelist should default to None (not enforced)."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
        )

        assert config.eco_whitelist is None

    def test_is_eco_allowed_rejects_non_whitelisted_eco(self) -> None:
        """When whitelist is configured, non-whitelisted ECOs should be rejected."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_whitelist=["approved_eco"],
        )

        allowed, reason = config.is_eco_allowed("unapproved_eco")
        assert not allowed
        assert "whitelist" in reason.lower()
        assert "unapproved_eco" in reason

    def test_is_eco_allowed_accepts_whitelisted_eco(self) -> None:
        """Whitelisted ECOs should be allowed."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_whitelist=["approved_eco"],
        )

        allowed, reason = config.is_eco_allowed("approved_eco")
        assert allowed
        assert reason is None

    def test_whitelist_with_multiple_ecos(self) -> None:
        """Whitelist should support multiple ECOs."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_whitelist=["eco1", "eco2", "eco3"],
        )

        # All whitelisted ECOs should be allowed
        for eco_name in ["eco1", "eco2", "eco3"]:
            allowed, reason = config.is_eco_allowed(eco_name)
            assert allowed
            assert reason is None

        # Non-whitelisted ECO should be rejected
        allowed, reason = config.is_eco_allowed("eco4")
        assert not allowed

    def test_whitelist_none_allows_all_ecos(self) -> None:
        """When whitelist is None, all ECOs should be allowed (no restriction)."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_whitelist=None,
        )

        # Any ECO should be allowed
        for eco_name in ["eco1", "eco2", "random_eco"]:
            allowed, reason = config.is_eco_allowed(eco_name)
            assert allowed
            assert reason is None


class TestBlacklistWhitelistInteraction:
    """Test interaction between blacklist and whitelist."""

    def test_blacklist_and_whitelist_cannot_overlap(self) -> None:
        """Configuration with overlapping blacklist and whitelist should fail validation."""
        with pytest.raises(ValueError, match="cannot be in both blacklist and whitelist"):
            config = StudyConfig(
                name="test_study",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage1",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=10,
                        survivor_count=5,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path="/path/to/snapshot",
                eco_blacklist=["eco1", "eco2"],
                eco_whitelist=["eco2", "eco3"],  # eco2 is in both!
            )
            config.validate()

    def test_whitelist_with_blacklist_enforces_both(self) -> None:
        """When both are configured, whitelist is checked first, then blacklist."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_blacklist=["suspicious_eco"],
            eco_whitelist=["approved_eco1", "approved_eco2"],
        )

        # ECO not in whitelist should be rejected (whitelist check first)
        allowed, reason = config.is_eco_allowed("random_eco")
        assert not allowed
        assert "whitelist" in reason.lower()

        # ECO in whitelist should be allowed
        allowed, reason = config.is_eco_allowed("approved_eco1")
        assert allowed

        # Blacklisted ECO not in whitelist should be rejected with whitelist message
        allowed, reason = config.is_eco_allowed("suspicious_eco")
        assert not allowed
        assert "whitelist" in reason.lower()


class TestECOFilteringFromYAML:
    """Test loading ECO filtering from YAML configuration."""

    def test_load_study_with_blacklist_from_yaml(self) -> None:
        """Load Study configuration with ECO blacklist from YAML."""
        config_data = {
            "name": "blacklist_study",
            "safety_domain": "sandbox",
            "base_case_name": "base",
            "pdk": "Nangate45",
            "snapshot_path": "/path/to/snapshot",
            "eco_blacklist": ["bad_eco1", "bad_eco2"],
            "stages": [
                {
                    "name": "stage1",
                    "execution_mode": "sta_only",
                    "trial_budget": 10,
                    "survivor_count": 5,
                    "allowed_eco_classes": ["topology_neutral"],
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = load_study_config(config_path)
            assert config.eco_blacklist == ["bad_eco1", "bad_eco2"]

            # Verify filtering works
            allowed, _ = config.is_eco_allowed("bad_eco1")
            assert not allowed
            allowed, _ = config.is_eco_allowed("good_eco")
            assert allowed
        finally:
            Path(config_path).unlink()

    def test_load_study_with_whitelist_from_yaml(self) -> None:
        """Load Study configuration with ECO whitelist from YAML."""
        config_data = {
            "name": "whitelist_study",
            "safety_domain": "locked",
            "base_case_name": "base",
            "pdk": "Nangate45",
            "snapshot_path": "/path/to/snapshot",
            "eco_whitelist": ["approved_eco1", "approved_eco2"],
            "stages": [
                {
                    "name": "stage1",
                    "execution_mode": "sta_only",
                    "trial_budget": 10,
                    "survivor_count": 5,
                    "allowed_eco_classes": ["topology_neutral"],
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = load_study_config(config_path)
            assert config.eco_whitelist == ["approved_eco1", "approved_eco2"]

            # Verify filtering works
            allowed, _ = config.is_eco_allowed("approved_eco1")
            assert allowed
            allowed, _ = config.is_eco_allowed("unapproved_eco")
            assert not allowed
        finally:
            Path(config_path).unlink()

    def test_load_study_without_blacklist_or_whitelist(self) -> None:
        """Study without blacklist/whitelist should use defaults."""
        config_data = {
            "name": "unrestricted_study",
            "safety_domain": "sandbox",
            "base_case_name": "base",
            "pdk": "Nangate45",
            "snapshot_path": "/path/to/snapshot",
            "stages": [
                {
                    "name": "stage1",
                    "execution_mode": "sta_only",
                    "trial_budget": 10,
                    "survivor_count": 5,
                    "allowed_eco_classes": ["topology_neutral"],
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = load_study_config(config_path)
            assert config.eco_blacklist == []
            assert config.eco_whitelist is None

            # All ECOs should be allowed
            for eco_name in ["eco1", "eco2", "any_eco"]:
                allowed, _ = config.is_eco_allowed(eco_name)
                assert allowed
        finally:
            Path(config_path).unlink()


class TestECOFilteringUseCases:
    """Test realistic use cases for ECO filtering."""

    def test_locked_domain_with_whitelist_for_regression(self) -> None:
        """Locked safety domain typically uses whitelist for regression testing."""
        config = StudyConfig(
            name="regression_study",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="stable_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_whitelist=["known_good_eco1", "known_good_eco2"],
        )

        # Only whitelisted ECOs should be allowed
        allowed, _ = config.is_eco_allowed("known_good_eco1")
        assert allowed

        allowed, reason = config.is_eco_allowed("experimental_eco")
        assert not allowed
        assert "whitelist" in reason.lower()

    def test_sandbox_domain_with_blacklist_for_exploration(self) -> None:
        """Sandbox domain uses blacklist to exclude known-bad ECOs while exploring."""
        config = StudyConfig(
            name="exploratory_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="experimental_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=50,
                    survivor_count=10,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                        ECOClass.PLACEMENT_LOCAL,
                    ],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_blacklist=["catastrophic_eco", "known_crash_eco"],
        )

        # Most ECOs should be allowed
        allowed, _ = config.is_eco_allowed("new_experimental_eco")
        assert allowed

        # Blacklisted ECOs should be rejected
        allowed, reason = config.is_eco_allowed("catastrophic_eco")
        assert not allowed
        assert "blacklisted" in reason.lower()

    def test_blacklist_identifies_eco_by_name(self) -> None:
        """Blacklist should provide clear identification of blocked ECO."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/path/to/snapshot",
            eco_blacklist=["buffer_storm_eco"],
        )

        allowed, reason = config.is_eco_allowed("buffer_storm_eco")
        assert not allowed
        assert "buffer_storm_eco" in reason
        assert "blacklisted" in reason.lower()
