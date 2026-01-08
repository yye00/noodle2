"""Tests for notification hook system."""

import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Any
from unittest.mock import patch

import pytest

from src.controller.notifications import (
    NotificationConfig,
    NotificationEvent,
    NotificationHook,
    NotificationPayload,
    create_study_completion_payload,
    create_study_failure_payload,
    create_study_started_payload,
)


class TestNotificationConfig:
    """Tests for NotificationConfig."""

    def test_create_minimal_config(self) -> None:
        """Test creating minimal notification configuration."""
        config = NotificationConfig()
        assert config.webhook_url is None
        assert NotificationEvent.STUDY_COMPLETED in config.events
        assert NotificationEvent.STUDY_FAILED in config.events
        assert config.timeout_seconds == 10
        assert config.retry_count == 3

    def test_create_with_webhook_url(self) -> None:
        """Test creating configuration with webhook URL."""
        config = NotificationConfig(webhook_url="https://example.com/webhook")
        assert config.webhook_url == "https://example.com/webhook"

    def test_invalid_webhook_url_protocol(self) -> None:
        """Test that invalid webhook URL protocol raises error."""
        with pytest.raises(ValueError, match="must start with http:// or https://"):
            NotificationConfig(webhook_url="ftp://example.com")

    def test_invalid_timeout(self) -> None:
        """Test that invalid timeout raises error."""
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            NotificationConfig(
                webhook_url="https://example.com",
                timeout_seconds=0
            )

    def test_invalid_retry_count(self) -> None:
        """Test that negative retry count raises error."""
        with pytest.raises(ValueError, match="retry_count must be non-negative"):
            NotificationConfig(
                webhook_url="https://example.com",
                retry_count=-1
            )

    def test_custom_events(self) -> None:
        """Test configuring custom events."""
        config = NotificationConfig(
            webhook_url="https://example.com",
            events=[NotificationEvent.STUDY_STARTED]
        )
        assert len(config.events) == 1
        assert NotificationEvent.STUDY_STARTED in config.events
        assert NotificationEvent.STUDY_COMPLETED not in config.events

    def test_custom_headers(self) -> None:
        """Test configuring custom headers."""
        config = NotificationConfig(
            webhook_url="https://example.com",
            custom_headers={"Authorization": "Bearer token123"}
        )
        assert config.custom_headers["Authorization"] == "Bearer token123"


class TestNotificationPayload:
    """Tests for NotificationPayload."""

    def test_create_completion_payload(self) -> None:
        """Test creating study completion payload."""
        timestamp = datetime.now().isoformat()
        summary = {"total_trials": 10, "winner": "case_0_0"}

        payload = create_study_completion_payload(
            study_name="test_study",
            timestamp=timestamp,
            summary=summary
        )

        assert payload.event == NotificationEvent.STUDY_COMPLETED
        assert payload.study_name == "test_study"
        assert payload.timestamp == timestamp
        assert payload.status == "success"
        assert payload.summary == summary
        assert payload.error_details is None

    def test_create_failure_payload(self) -> None:
        """Test creating study failure payload."""
        timestamp = datetime.now().isoformat()
        error_details = {
            "failure_type": "base_case_blocked",
            "message": "Base case failed to execute"
        }

        payload = create_study_failure_payload(
            study_name="test_study",
            timestamp=timestamp,
            error_details=error_details
        )

        assert payload.event == NotificationEvent.STUDY_FAILED
        assert payload.study_name == "test_study"
        assert payload.status == "failed"
        assert payload.error_details == error_details

    def test_create_started_payload(self) -> None:
        """Test creating study started payload."""
        timestamp = datetime.now().isoformat()
        summary = {"stages": 3, "pdk": "Nangate45"}

        payload = create_study_started_payload(
            study_name="test_study",
            timestamp=timestamp,
            summary=summary
        )

        assert payload.event == NotificationEvent.STUDY_STARTED
        assert payload.status == "started"

    def test_payload_to_dict(self) -> None:
        """Test converting payload to dictionary."""
        timestamp = datetime.now().isoformat()
        payload = NotificationPayload(
            event=NotificationEvent.STUDY_COMPLETED,
            study_name="test_study",
            timestamp=timestamp,
            status="success",
            summary={"trials": 5}
        )

        data = payload.to_dict()
        assert data["event"] == "study_completed"
        assert data["study_name"] == "test_study"
        assert data["timestamp"] == timestamp
        assert data["status"] == "success"
        assert data["summary"]["trials"] == 5
        assert "error_details" not in data

    def test_payload_to_dict_with_error(self) -> None:
        """Test converting failure payload to dictionary."""
        timestamp = datetime.now().isoformat()
        payload = NotificationPayload(
            event=NotificationEvent.STUDY_FAILED,
            study_name="test_study",
            timestamp=timestamp,
            status="failed",
            summary={},
            error_details={"type": "timeout"}
        )

        data = payload.to_dict()
        assert "error_details" in data
        assert data["error_details"]["type"] == "timeout"

    def test_payload_to_json(self) -> None:
        """Test converting payload to JSON."""
        timestamp = datetime.now().isoformat()
        payload = NotificationPayload(
            event=NotificationEvent.STUDY_COMPLETED,
            study_name="test_study",
            timestamp=timestamp,
            status="success",
            summary={"trials": 5}
        )

        json_str = payload.to_json()
        data = json.loads(json_str)
        assert data["event"] == "study_completed"
        assert data["study_name"] == "test_study"


class TestNotificationHook:
    """Tests for NotificationHook."""

    def test_should_notify_no_webhook(self) -> None:
        """Test that notifications are skipped when no webhook is configured."""
        config = NotificationConfig()
        hook = NotificationHook(config)

        assert not hook.should_notify(NotificationEvent.STUDY_COMPLETED)

    def test_should_notify_with_webhook(self) -> None:
        """Test notification check with webhook configured."""
        config = NotificationConfig(
            webhook_url="https://example.com/webhook",
            events=[NotificationEvent.STUDY_COMPLETED]
        )
        hook = NotificationHook(config)

        assert hook.should_notify(NotificationEvent.STUDY_COMPLETED)
        assert not hook.should_notify(NotificationEvent.STUDY_STARTED)

    def test_send_notification_no_webhook(self) -> None:
        """Test sending notification when no webhook is configured."""
        config = NotificationConfig()  # No webhook URL
        hook = NotificationHook(config)

        payload = create_study_completion_payload(
            study_name="test",
            timestamp=datetime.now().isoformat(),
            summary={}
        )

        success, error = hook.send(payload)
        assert success  # Returns success because notification is skipped
        assert error is None

    def test_send_notification_event_not_configured(self) -> None:
        """Test sending notification for event not in configuration."""
        config = NotificationConfig(
            webhook_url="https://example.com/webhook",
            events=[NotificationEvent.STUDY_COMPLETED]  # Only completion
        )
        hook = NotificationHook(config)

        payload = create_study_started_payload(
            study_name="test",
            timestamp=datetime.now().isoformat(),
            summary={}
        )

        success, error = hook.send(payload)
        assert success  # Returns success because event is not configured
        assert error is None


# Mock HTTP server for testing webhooks
class MockWebhookHandler(BaseHTTPRequestHandler):
    """Mock webhook handler for testing."""

    received_payloads: list[dict[str, Any]] = []

    def do_POST(self) -> None:
        """Handle POST request."""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))
        MockWebhookHandler.received_payloads.append(payload)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = json.dumps({"status": "received"})
        self.wfile.write(response.encode('utf-8'))

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress log messages."""
        pass


class TestNotificationIntegration:
    """Integration tests for notification system."""

    @pytest.fixture
    def mock_server(self) -> tuple[HTTPServer, str]:
        """Start a mock webhook server."""
        MockWebhookHandler.received_payloads = []
        server = HTTPServer(('localhost', 0), MockWebhookHandler)
        port = server.server_port
        url = f"http://localhost:{port}/webhook"

        # Start server in background thread
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        yield server, url

        server.shutdown()

    def test_send_notification_success(self, mock_server: tuple[HTTPServer, str]) -> None:
        """Test successfully sending notification to webhook."""
        server, url = mock_server

        config = NotificationConfig(
            webhook_url=url,
            events=[NotificationEvent.STUDY_COMPLETED]
        )
        hook = NotificationHook(config)

        timestamp = datetime.now().isoformat()
        payload = create_study_completion_payload(
            study_name="test_study",
            timestamp=timestamp,
            summary={"trials": 10, "winner": "case_0_0"}
        )

        success, error = hook.send(payload)

        assert success
        assert error is None
        assert len(MockWebhookHandler.received_payloads) == 1

        received = MockWebhookHandler.received_payloads[0]
        assert received["event"] == "study_completed"
        assert received["study_name"] == "test_study"
        assert received["summary"]["trials"] == 10

    def test_send_failure_notification(self, mock_server: tuple[HTTPServer, str]) -> None:
        """Test sending failure notification."""
        server, url = mock_server

        config = NotificationConfig(
            webhook_url=url,
            events=[NotificationEvent.STUDY_FAILED]
        )
        hook = NotificationHook(config)

        timestamp = datetime.now().isoformat()
        payload = create_study_failure_payload(
            study_name="failed_study",
            timestamp=timestamp,
            error_details={"type": "base_case_blocked", "message": "Failed to run"}
        )

        success, error = hook.send(payload)

        assert success
        assert error is None
        assert len(MockWebhookHandler.received_payloads) == 1

        received = MockWebhookHandler.received_payloads[0]
        assert received["event"] == "study_failed"
        assert received["status"] == "failed"
        assert "error_details" in received

    def test_send_notification_with_custom_headers(self, mock_server: tuple[HTTPServer, str]) -> None:
        """Test sending notification with custom headers."""
        server, url = mock_server

        config = NotificationConfig(
            webhook_url=url,
            custom_headers={"X-Custom-Header": "test-value"}
        )
        hook = NotificationHook(config)

        timestamp = datetime.now().isoformat()
        payload = create_study_completion_payload(
            study_name="test",
            timestamp=timestamp,
            summary={}
        )

        success, error = hook.send(payload)
        assert success


class TestNotificationErrors:
    """Tests for notification error handling."""

    def test_send_to_invalid_url(self) -> None:
        """Test sending notification to invalid URL."""
        config = NotificationConfig(
            webhook_url="http://localhost:99999/webhook",  # Invalid port
            timeout_seconds=1,
            retry_count=0  # No retries
        )
        hook = NotificationHook(config)

        timestamp = datetime.now().isoformat()
        payload = create_study_completion_payload(
            study_name="test",
            timestamp=timestamp,
            summary={}
        )

        success, error = hook.send(payload)

        assert not success
        assert error is not None
        assert "error" in error.lower() or "refused" in error.lower()

    def test_retry_on_failure(self) -> None:
        """Test that notifications are retried on failure."""
        config = NotificationConfig(
            webhook_url="http://localhost:99999/webhook",
            timeout_seconds=1,
            retry_count=2
        )
        hook = NotificationHook(config)

        timestamp = datetime.now().isoformat()
        payload = create_study_completion_payload(
            study_name="test",
            timestamp=timestamp,
            summary={}
        )

        # Should fail after retries
        with patch.object(hook, '_send_request') as mock_send:
            mock_send.return_value = (False, "Connection refused")
            success, error = hook.send(payload)

            assert not success
            assert mock_send.call_count == 3  # Initial + 2 retries
