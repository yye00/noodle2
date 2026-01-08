"""Tests for Study notification configuration integration."""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.controller.notifications import NotificationConfig, NotificationEvent
from src.controller.study import load_study_config
from src.controller.types import ExecutionMode, SafetyDomain


class TestStudyNotificationConfig:
    """Tests for notification configuration in Study."""

    def test_study_config_with_webhook_url(self) -> None:
        """Test Study configuration with webhook URL."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_data = {
                "name": "test_study",
                "safety_domain": "sandbox",
                "base_case_name": "nangate45_base",
                "pdk": "Nangate45",
                "snapshot_path": "/path/to/snapshot",
                "notification_webhook_url": "https://example.com/webhook",
                "stages": [
                    {
                        "name": "stage_0",
                        "execution_mode": "sta_only",
                        "trial_budget": 10,
                        "survivor_count": 5,
                        "allowed_eco_classes": []
                    }
                ]
            }
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            study_config = load_study_config(config_path)
            assert study_config.notification_webhook_url == "https://example.com/webhook"
            assert study_config.notification_events is None  # Defaults to None
        finally:
            Path(config_path).unlink()

    def test_study_config_with_custom_events(self) -> None:
        """Test Study configuration with custom notification events."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_data = {
                "name": "test_study",
                "safety_domain": "guarded",
                "base_case_name": "nangate45_base",
                "pdk": "Nangate45",
                "snapshot_path": "/path/to/snapshot",
                "notification_webhook_url": "https://example.com/webhook",
                "notification_events": ["study_completed", "study_failed", "study_started"],
                "stages": [
                    {
                        "name": "stage_0",
                        "execution_mode": "sta_only",
                        "trial_budget": 10,
                        "survivor_count": 5,
                        "allowed_eco_classes": []
                    }
                ]
            }
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            study_config = load_study_config(config_path)
            assert study_config.notification_webhook_url == "https://example.com/webhook"
            assert study_config.notification_events == ["study_completed", "study_failed", "study_started"]
        finally:
            Path(config_path).unlink()

    def test_study_config_without_notifications(self) -> None:
        """Test Study configuration without notification settings."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_data = {
                "name": "test_study",
                "safety_domain": "sandbox",
                "base_case_name": "nangate45_base",
                "pdk": "Nangate45",
                "snapshot_path": "/path/to/snapshot",
                "stages": [
                    {
                        "name": "stage_0",
                        "execution_mode": "sta_only",
                        "trial_budget": 10,
                        "survivor_count": 5,
                        "allowed_eco_classes": []
                    }
                ]
            }
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            study_config = load_study_config(config_path)
            assert study_config.notification_webhook_url is None
            assert study_config.notification_events is None
        finally:
            Path(config_path).unlink()

    def test_create_notification_config_from_study(self) -> None:
        """Test creating NotificationConfig from StudyConfig."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_data = {
                "name": "test_study",
                "safety_domain": "sandbox",
                "base_case_name": "nangate45_base",
                "pdk": "Nangate45",
                "snapshot_path": "/path/to/snapshot",
                "notification_webhook_url": "https://example.com/webhook",
                "notification_events": ["study_completed"],
                "stages": [
                    {
                        "name": "stage_0",
                        "execution_mode": "sta_only",
                        "trial_budget": 10,
                        "survivor_count": 5,
                        "allowed_eco_classes": []
                    }
                ]
            }
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            study_config = load_study_config(config_path)

            # Create NotificationConfig from Study config
            if study_config.notification_webhook_url:
                events = [
                    NotificationEvent(e) for e in study_config.notification_events
                ] if study_config.notification_events else None

                notification_config = NotificationConfig(
                    webhook_url=study_config.notification_webhook_url,
                    events=events or [NotificationEvent.STUDY_COMPLETED, NotificationEvent.STUDY_FAILED]
                )

                assert notification_config.webhook_url == "https://example.com/webhook"
                assert len(notification_config.events) == 1
                assert NotificationEvent.STUDY_COMPLETED in notification_config.events
        finally:
            Path(config_path).unlink()
