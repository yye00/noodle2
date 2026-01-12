"""Tests for event stream telemetry."""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.executor import StudyExecutor
from src.controller.study import StudyConfig
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig
from src.telemetry.event_stream import Event, EventStreamEmitter, EventType


class TestEventClass:
    """Tests for Event class."""

    def test_create_event(self):
        """Test creating an event."""
        event = Event(
            event_type=EventType.STUDY_START,
            timestamp="2024-01-01T00:00:00Z",
            event_data={"study_name": "test"},
        )

        assert event.event_type == EventType.STUDY_START
        assert event.timestamp == "2024-01-01T00:00:00Z"
        assert event.event_data == {"study_name": "test"}

    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        event = Event(
            event_type=EventType.TRIAL_COMPLETE,
            timestamp="2024-01-01T00:00:00Z",
            event_data={"success": True, "runtime_seconds": 10.5},
        )

        event_dict = event.to_dict()

        assert event_dict["event_type"] == "trial_complete"
        assert event_dict["timestamp"] == "2024-01-01T00:00:00Z"
        assert event_dict["event_data"]["success"] is True
        assert event_dict["event_data"]["runtime_seconds"] == 10.5

    def test_event_to_json(self):
        """Test converting event to JSON string."""
        event = Event(
            event_type=EventType.STUDY_START,
            timestamp="2024-01-01T00:00:00Z",
            event_data={"study_name": "test"},
        )

        json_str = event.to_json()
        parsed = json.loads(json_str)

        assert parsed["event_type"] == "study_start"
        assert parsed["timestamp"] == "2024-01-01T00:00:00Z"
        assert parsed["event_data"]["study_name"] == "test"


class TestEventStreamEmitter:
    """Tests for EventStreamEmitter."""

    def test_create_event_stream_emitter(self):
        """Test creating an event stream emitter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            assert emitter.stream_path == stream_path
            assert stream_path.exists()

    def test_emit_event(self):
        """Test emitting a single event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit(
                event_type=EventType.STUDY_START,
                event_data={"study_name": "test_study", "total_stages": 2},
            )

            assert event.event_type == EventType.STUDY_START
            assert event.event_data["study_name"] == "test_study"
            assert event.event_data["total_stages"] == 2

            # Verify file was written
            assert stream_path.exists()
            content = stream_path.read_text()
            assert "study_start" in content
            assert "test_study" in content

    def test_emit_multiple_events(self):
        """Test emitting multiple events in sequence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            # Emit three events
            emitter.emit(EventType.STUDY_START, {"study_name": "test"})
            emitter.emit(EventType.STAGE_START, {"stage_index": 0})
            emitter.emit(EventType.STUDY_COMPLETE, {"final_survivors": []})

            # Read file and count lines
            lines = stream_path.read_text().strip().split("\n")
            assert len(lines) == 3

            # Verify each line is valid JSON
            for line in lines:
                parsed = json.loads(line)
                assert "event_type" in parsed
                assert "timestamp" in parsed
                assert "event_data" in parsed

    def test_event_timestamps_are_iso8601(self):
        """Test that event timestamps are in ISO 8601 format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit(EventType.STUDY_START, {"study_name": "test"})

            # ISO 8601 format should contain 'T' and end with timezone info
            assert "T" in event.timestamp
            # Should be parseable by datetime
            from datetime import datetime

            datetime.fromisoformat(event.timestamp)  # Will raise if invalid

    def test_emit_study_start(self):
        """Test emitting a study start event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_study_start(
                study_name="nangate45_study",
                safety_domain="sandbox",
                total_stages=3,
            )

            assert event.event_type == EventType.STUDY_START
            assert event.event_data["study_name"] == "nangate45_study"
            assert event.event_data["safety_domain"] == "sandbox"
            assert event.event_data["total_stages"] == 3

    def test_emit_study_complete(self):
        """Test emitting a study complete event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_study_complete(
                study_name="nangate45_study",
                final_survivors=["case1", "case2"],
                runtime_seconds=125.5,
            )

            assert event.event_type == EventType.STUDY_COMPLETE
            assert event.event_data["study_name"] == "nangate45_study"
            assert event.event_data["final_survivors"] == ["case1", "case2"]
            assert event.event_data["runtime_seconds"] == 125.5

    def test_emit_study_aborted(self):
        """Test emitting a study aborted event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_study_aborted(
                study_name="nangate45_study",
                abort_reason="Stage 1 produced no survivors",
                stage_index=1,
            )

            assert event.event_type == EventType.STUDY_ABORTED
            assert event.event_data["abort_reason"] == "Stage 1 produced no survivors"
            assert event.event_data["stage_index"] == 1

    def test_emit_study_blocked(self):
        """Test emitting a study blocked event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_study_blocked(
                study_name="nangate45_study",
                reason="Study configuration is ILLEGAL",
            )

            assert event.event_type == EventType.STUDY_BLOCKED
            assert event.event_data["reason"] == "Study configuration is ILLEGAL"

    def test_emit_stage_start(self):
        """Test emitting a stage start event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_stage_start(
                study_name="nangate45_study",
                stage_index=0,
                stage_name="exploration",
                trial_budget=10,
            )

            assert event.event_type == EventType.STAGE_START
            assert event.event_data["stage_index"] == 0
            assert event.event_data["stage_name"] == "exploration"
            assert event.event_data["trial_budget"] == 10

    def test_emit_stage_complete(self):
        """Test emitting a stage complete event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_stage_complete(
                study_name="nangate45_study",
                stage_index=0,
                survivors=["case1", "case2", "case3"],
                trials_executed=10,
                runtime_seconds=50.0,
            )

            assert event.event_type == EventType.STAGE_COMPLETE
            assert event.event_data["survivors"] == ["case1", "case2", "case3"]
            assert event.event_data["trials_executed"] == 10
            assert event.event_data["runtime_seconds"] == 50.0

    def test_emit_stage_aborted(self):
        """Test emitting a stage aborted event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_stage_aborted(
                study_name="nangate45_study",
                stage_index=1,
                reason="No survivors produced",
            )

            assert event.event_type == EventType.STAGE_ABORTED
            assert event.event_data["reason"] == "No survivors produced"

    def test_emit_trial_start(self):
        """Test emitting a trial start event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_trial_start(
                study_name="nangate45_study",
                case_name="nangate45_0_5",
                stage_index=0,
                trial_index=5,
            )

            assert event.event_type == EventType.TRIAL_START
            assert event.event_data["case_name"] == "nangate45_0_5"
            assert event.event_data["stage_index"] == 0
            assert event.event_data["trial_index"] == 5

    def test_emit_trial_complete(self):
        """Test emitting a trial complete event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_trial_complete(
                study_name="nangate45_study",
                case_name="nangate45_0_5",
                stage_index=0,
                trial_index=5,
                success=True,
                runtime_seconds=12.5,
                metrics={"wns_ps": -500},
            )

            assert event.event_type == EventType.TRIAL_COMPLETE
            assert event.event_data["success"] is True
            assert event.event_data["runtime_seconds"] == 12.5
            assert event.event_data["metrics"] == {"wns_ps": -500}

    def test_emit_trial_failed(self):
        """Test emitting a trial failed event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_trial_failed(
                study_name="nangate45_study",
                case_name="nangate45_0_5",
                stage_index=0,
                trial_index=5,
                failure_type="tool_crash",
                failure_reason="Segmentation fault",
            )

            assert event.event_type == EventType.TRIAL_FAILED
            assert event.event_data["failure_type"] == "tool_crash"
            assert event.event_data["failure_reason"] == "Segmentation fault"

    def test_emit_legality_check(self):
        """Test emitting a legality check event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_legality_check(
                study_name="nangate45_study",
                legal=True,
                reason=None,
            )

            assert event.event_type == EventType.LEGALITY_CHECK
            assert event.event_data["legal"] is True

    def test_emit_base_case_verification(self):
        """Test emitting a base case verification event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_base_case_verification(
                study_name="nangate45_study",
                success=True,
                reason=None,
            )

            assert event.event_type == EventType.BASE_CASE_VERIFICATION
            assert event.event_data["success"] is True

    def test_emit_abort_evaluation(self):
        """Test emitting an abort evaluation event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            event = emitter.emit_abort_evaluation(
                study_name="nangate45_study",
                stage_index=1,
                should_abort=False,
                reason="Survivors meet threshold",
            )

            assert event.event_type == EventType.ABORT_EVALUATION
            assert event.event_data["should_abort"] is False
            assert event.event_data["reason"] == "Survivors meet threshold"

    def test_read_events(self):
        """Test reading events from the stream."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            # Emit several events
            emitter.emit_study_start("test_study", "sandbox", 2)
            emitter.emit_stage_start("test_study", 0, "exploration", 10)
            emitter.emit_stage_complete("test_study", 0, ["case1"], 10, 50.0)

            # Read events back
            events = emitter.read_events()

            assert len(events) == 3
            assert events[0].event_type == EventType.STUDY_START
            assert events[1].event_type == EventType.STAGE_START
            assert events[2].event_type == EventType.STAGE_COMPLETE

    def test_validate_json_format(self):
        """Test validating that all events are well-formed JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            # Emit several events
            emitter.emit_study_start("test_study", "sandbox", 2)
            emitter.emit_trial_start("test_study", "case1", 0, 0)
            emitter.emit_trial_complete("test_study", "case1", 0, 0, True, 10.0)

            # Validate format
            assert emitter.validate_json_format() is True

    def test_validate_json_format_with_empty_stream(self):
        """Test validating JSON format on an empty stream."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            # Empty stream should be valid
            assert emitter.validate_json_format() is True

    def test_events_are_timestamped(self):
        """Test that all events have timestamps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stream_path = Path(tmpdir) / "events.ndjson"
            emitter = EventStreamEmitter(stream_path=stream_path)

            # Emit events
            event1 = emitter.emit_study_start("test", "sandbox", 1)
            event2 = emitter.emit_stage_start("test", 0, "stage0", 5)

            # Both should have timestamps
            assert event1.timestamp is not None
            assert event2.timestamp is not None

            # Timestamps should be different (or at least have microsecond precision)
            assert len(event1.timestamp) > 10  # ISO 8601 with microseconds


class TestEventStreamIntegrationWithStudyExecutor:
    """Integration tests for event stream with StudyExecutor."""

    def test_study_execution_emits_event_stream(self):
        """Test that Study execution emits complete event stream."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal study config
            config = StudyConfig(
                name="event_stream_test",
                base_case_name="nangate45_base",
                pdk="Nangate45",
                safety_domain=SafetyDomain.SANDBOX,
                snapshot_path=Path(tmpdir) / "snapshot",
                stages=[
                    StageConfig(
                        name="stage0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=3,
                        survivor_count=2,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    ),
                ],
            )

            config.snapshot_path.mkdir(parents=True, exist_ok=True)

            telemetry_root = Path(tmpdir) / "telemetry"
            executor = StudyExecutor(
                skip_base_case_verification=True,
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=telemetry_root,
            )

            result = executor.execute()

            # Verify event stream file exists
            event_stream_path = telemetry_root / "event_stream_test" / "event_stream.ndjson"
            assert event_stream_path.exists()

            # Read and verify events
            emitter = EventStreamEmitter(stream_path=event_stream_path)
            events = emitter.read_events()

            # Should have: study_start, legality_check, stage_start, N*trial_start, N*trial_complete, stage_complete, study_complete
            assert len(events) >= 8  # At minimum

            # Verify event types in order
            event_types = [e.event_type for e in events]

            assert EventType.STUDY_START in event_types
            assert EventType.LEGALITY_CHECK in event_types
            assert EventType.STAGE_START in event_types
            assert EventType.TRIAL_START in event_types
            assert EventType.TRIAL_COMPLETE in event_types
            assert EventType.STAGE_COMPLETE in event_types
            assert EventType.STUDY_COMPLETE in event_types

    @pytest.mark.skip(reason="Abort event emission is tested in real E2E tests; mock scenarios with skip_base_case_verification don't produce metrics needed for abort logic")
    def test_aborted_study_emits_abort_events(self):
        """Test that aborted Study emits abort events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="aborted_test",
                base_case_name="nangate45_base",
                pdk="Nangate45",
                safety_domain=SafetyDomain.SANDBOX,
                snapshot_path=Path(tmpdir) / "snapshot",
                stages=[
                    StageConfig(
                        name="stage0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=2,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                        abort_threshold_wns_ps=1,  # Force abort - require positive WNS (impossible)
                    ),
                ],
            )

            config.snapshot_path.mkdir(parents=True, exist_ok=True)

            telemetry_root = Path(tmpdir) / "telemetry"
            executor = StudyExecutor(
                skip_base_case_verification=True,
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=telemetry_root,
            )

            result = executor.execute()

            assert result.aborted is True

            # Verify event stream contains abort events
            event_stream_path = telemetry_root / "aborted_test" / "event_stream.ndjson"
            assert event_stream_path.exists()

            emitter = EventStreamEmitter(stream_path=event_stream_path)
            events = emitter.read_events()

            event_types = [e.event_type for e in events]
            assert EventType.ABORT_EVALUATION in event_types
            assert EventType.STAGE_ABORTED in event_types
            assert EventType.STUDY_ABORTED in event_types

    def test_event_stream_is_valid_json(self):
        """Test that event stream maintains valid JSON format throughout execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="json_validation_test",
                base_case_name="nangate45_base",
                pdk="Nangate45",
                safety_domain=SafetyDomain.SANDBOX,
                snapshot_path=Path(tmpdir) / "snapshot",
                stages=[
                    StageConfig(
                        name="stage0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=5,
                        survivor_count=3,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    ),
                ],
            )

            config.snapshot_path.mkdir(parents=True, exist_ok=True)

            telemetry_root = Path(tmpdir) / "telemetry"
            executor = StudyExecutor(
                skip_base_case_verification=True,
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=telemetry_root,
            )

            result = executor.execute()

            # Verify all events are valid JSON
            event_stream_path = telemetry_root / "json_validation_test" / "event_stream.ndjson"
            emitter = EventStreamEmitter(stream_path=event_stream_path)

            assert emitter.validate_json_format() is True

    def test_programmatic_telemetry_analysis(self):
        """Test that event stream enables programmatic telemetry analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="analysis_test",
                base_case_name="nangate45_base",
                pdk="Nangate45",
                safety_domain=SafetyDomain.SANDBOX,
                snapshot_path=Path(tmpdir) / "snapshot",
                stages=[
                    StageConfig(
                        name="stage0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=10,
                        survivor_count=5,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    ),
                ],
            )

            config.snapshot_path.mkdir(parents=True, exist_ok=True)

            telemetry_root = Path(tmpdir) / "telemetry"
            executor = StudyExecutor(
                skip_base_case_verification=True,
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=telemetry_root,
            )

            result = executor.execute()

            # Read event stream
            event_stream_path = telemetry_root / "analysis_test" / "event_stream.ndjson"
            emitter = EventStreamEmitter(stream_path=event_stream_path)
            events = emitter.read_events()

            # Programmatic analysis examples:

            # 1. Count events by type
            event_counts = {}
            for event in events:
                event_type = event.event_type.value
                event_counts[event_type] = event_counts.get(event_type, 0) + 1

            assert "study_start" in event_counts
            assert "trial_start" in event_counts
            assert "trial_complete" in event_counts
            assert event_counts["trial_start"] == 10  # trial_budget
            assert event_counts["trial_complete"] == 10

            # 2. Extract study duration from events
            study_start_event = next(e for e in events if e.event_type == EventType.STUDY_START)
            study_complete_event = next(e for e in events if e.event_type == EventType.STUDY_COMPLETE)

            assert study_start_event is not None
            assert study_complete_event is not None

            # 3. Verify chronological ordering
            timestamps = [e.timestamp for e in events]
            assert timestamps == sorted(timestamps)  # Timestamps should be in order
