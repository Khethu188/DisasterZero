
"""
tests/unit/test_recovery.py
───────────────────────────
Tests for the recovery engine.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.recovery.base import RecoveryResult, RecoveryAction


class TestRecoveryAction:
    """Test individual recovery actions."""

    def test_successful_action(self, recovery_success):
        actions = recovery_success.actions
        assert len(actions) == 2
        assert all(a.success for a in actions)

    def test_action_has_duration(self, recovery_success):
        for action in recovery_success.actions:
            assert action.duration_seconds > 0

    def test_action_has_timestamps(self, recovery_success):
        for action in recovery_success.actions:
            assert action.started_at is not None
            assert action.completed_at is not None
            assert action.completed_at > action.started_at

    def test_action_target_populated(self, recovery_success):
        for action in recovery_success.actions:
            assert action.target != ""


class TestRecoveryResult:
    """Test recovery result data model."""

    def test_successful_recovery(self, recovery_success):
        r = recovery_success
        assert r.recovered is True
        assert r.records_lost == 0
        assert r.data_consistent is True

    def test_partial_recovery(self, recovery_partial):
        r = recovery_partial
        assert r.recovered is False
        assert r.records_lost > 0
        assert r.records_recovered > 0
        assert r.records_recovered + r.records_lost == 5000

    def test_failed_recovery(self, recovery_failed):
        r = recovery_failed
        assert r.recovered is False
        assert r.records_lost == 18420
        assert r.data_consistent is False

    def test_recovery_has_timeline(self, recovery_success):
        r = recovery_success
        assert r.recovery_start is not None
        assert r.recovery_end is not None
        assert r.recovery_end > r.recovery_start
        assert r.total_duration_seconds > 0

    def test_recovery_links_to_detection(self, recovery_success):
        assert recovery_success.detection is not None
        assert recovery_success.detection.detected is True

    def test_total_duration_matches_actions(self, recovery_success):
        action_total = sum(a.duration_seconds for a in recovery_success.actions)
        assert recovery_success.total_duration_seconds == pytest.approx(action_total, abs=1.0)


class TestDatabricksRecovery:
    """Test Databricks-specific recovery operations."""

    def test_repair_run_called(self, config, detection_job_failure, mock_databricks_api):
        """Recovery should trigger a repair run for failed jobs."""
        from src.recovery.databricks_recovery import DatabricksRecoveryEngine

        engine = DatabricksRecoveryEngine(config)
        result = engine.recover(detection_job_failure)

        # Verify repair API was called
        mock_databricks_api["post"].assert_called()
        assert result is not None

    def test_recovery_handles_api_failure(self, config, detection_job_failure, mock_databricks_api):
        """Recovery should handle API errors gracefully."""
        from src.recovery.databricks_recovery import DatabricksRecoveryEngine

        mock_databricks_api["post"].side_effect = Exception("API timeout")

        engine = DatabricksRecoveryEngine(config)
        result = engine.recover(detection_job_failure)

        assert result is not None
        assert result.recovered is False

    def test_recovery_records_all_actions(self, config, detection_job_failure, mock_databricks_api):
        """Every recovery step should be recorded as an action."""
        from src.recovery.databricks_recovery import DatabricksRecoveryEngine

        engine = DatabricksRecoveryEngine(config)
        result = engine.recover(detection_job_failure)

        assert len(result.actions) > 0
        for action in result.actions:
            assert action.action != ""
            assert action.target != ""

