"""Notification hooks for Study completion and failures."""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)


class NotificationEvent(str, Enum):
    """Types of notification events."""

    STUDY_STARTED = "study_started"
    STUDY_COMPLETED = "study_completed"
    STUDY_FAILED = "study_failed"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"


@dataclass
class NotificationConfig:
    """Configuration for notification hooks."""

    webhook_url: str | None = None
    events: list[NotificationEvent] = field(default_factory=lambda: [
        NotificationEvent.STUDY_COMPLETED,
        NotificationEvent.STUDY_FAILED
    ])
    timeout_seconds: int = 10
    retry_count: int = 3
    custom_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate notification configuration."""
        if self.webhook_url is not None:
            if not self.webhook_url.startswith(("http://", "https://")):
                raise ValueError("Webhook URL must start with http:// or https://")

        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")


@dataclass
class NotificationPayload:
    """Payload sent to notification webhooks."""

    event: NotificationEvent
    study_name: str
    timestamp: str  # ISO 8601 timestamp
    status: str  # "success", "failed", "started"
    summary: dict[str, Any] = field(default_factory=dict)
    error_details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dictionary for JSON serialization."""
        data: dict[str, Any] = {
            "event": self.event.value,
            "study_name": self.study_name,
            "timestamp": self.timestamp,
            "status": self.status,
            "summary": self.summary,
        }
        if self.error_details:
            data["error_details"] = self.error_details
        return data

    def to_json(self) -> str:
        """Convert payload to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class NotificationHook:
    """Handles sending notifications via webhooks."""

    def __init__(self, config: NotificationConfig):
        """Initialize notification hook.

        Args:
            config: Notification configuration
        """
        self.config = config

    def should_notify(self, event: NotificationEvent) -> bool:
        """Check if this event should trigger a notification.

        Args:
            event: The notification event

        Returns:
            True if notification should be sent
        """
        if self.config.webhook_url is None:
            return False
        return event in self.config.events

    def send(self, payload: NotificationPayload) -> tuple[bool, str | None]:
        """Send notification payload to webhook.

        Args:
            payload: The notification payload to send

        Returns:
            Tuple of (success: bool, error_message: str | None)
        """
        if not self.should_notify(payload.event):
            logger.debug(f"Skipping notification for event {payload.event} (not configured)")
            return True, None

        if self.config.webhook_url is None:
            logger.warning("Notification requested but webhook_url is None")
            return False, "No webhook URL configured"

        logger.info(f"Sending notification: {payload.event} for study {payload.study_name}")

        # Try with retries
        last_error = None
        for attempt in range(self.config.retry_count + 1):
            success, error = self._send_request(payload)
            if success:
                logger.info(f"Notification sent successfully (attempt {attempt + 1})")
                return True, None
            last_error = error
            if attempt < self.config.retry_count:
                logger.warning(f"Notification failed (attempt {attempt + 1}): {error}, retrying...")

        logger.error(f"Notification failed after {self.config.retry_count + 1} attempts: {last_error}")
        return False, last_error

    def _send_request(self, payload: NotificationPayload) -> tuple[bool, str | None]:
        """Send HTTP POST request to webhook.

        Args:
            payload: The notification payload

        Returns:
            Tuple of (success: bool, error_message: str | None)
        """
        if self.config.webhook_url is None:
            return False, "No webhook URL configured"

        try:
            # Prepare request
            data = payload.to_json().encode('utf-8')

            req = request.Request(
                self.config.webhook_url,
                data=data,
                method='POST'
            )

            # Set headers
            req.add_header('Content-Type', 'application/json')
            req.add_header('User-Agent', 'Noodle2/1.0')

            for key, value in self.config.custom_headers.items():
                req.add_header(key, value)

            # Send request
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                status_code = response.getcode()
                if 200 <= status_code < 300:
                    return True, None
                else:
                    return False, f"HTTP {status_code}"

        except HTTPError as e:
            return False, f"HTTP {e.code}: {e.reason}"
        except URLError as e:
            return False, f"URL error: {e.reason}"
        except Exception as e:
            return False, f"Unexpected error: {type(e).__name__}: {e}"


def create_study_completion_payload(
    study_name: str,
    timestamp: str,
    summary: dict[str, Any]
) -> NotificationPayload:
    """Create notification payload for Study completion.

    Args:
        study_name: Name of the completed Study
        timestamp: ISO 8601 timestamp
        summary: Study summary data

    Returns:
        NotificationPayload for study completion
    """
    return NotificationPayload(
        event=NotificationEvent.STUDY_COMPLETED,
        study_name=study_name,
        timestamp=timestamp,
        status="success",
        summary=summary
    )


def create_study_failure_payload(
    study_name: str,
    timestamp: str,
    error_details: dict[str, Any],
    summary: dict[str, Any] | None = None
) -> NotificationPayload:
    """Create notification payload for Study failure.

    Args:
        study_name: Name of the failed Study
        timestamp: ISO 8601 timestamp
        error_details: Details about the failure
        summary: Optional partial Study summary data

    Returns:
        NotificationPayload for study failure
    """
    return NotificationPayload(
        event=NotificationEvent.STUDY_FAILED,
        study_name=study_name,
        timestamp=timestamp,
        status="failed",
        summary=summary or {},
        error_details=error_details
    )


def create_study_started_payload(
    study_name: str,
    timestamp: str,
    summary: dict[str, Any]
) -> NotificationPayload:
    """Create notification payload for Study start.

    Args:
        study_name: Name of the Study
        timestamp: ISO 8601 timestamp
        summary: Study configuration summary

    Returns:
        NotificationPayload for study start
    """
    return NotificationPayload(
        event=NotificationEvent.STUDY_STARTED,
        study_name=study_name,
        timestamp=timestamp,
        status="started",
        summary=summary
    )
