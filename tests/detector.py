
"""
tests/unit/test_detector.py
───────────────────────────
Tests for the failure detection engine.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.detector.base import DetectionResult


class TestDetectionResult:
    """Test DetectionResult data model."""

    def test_detected_result_has_required_fields(self, detection_job_failure):
        d = detection_job_failure
        assert d.detected is True
        assert d.failure_type == "databricks_job_failure"
        assert d.target != ""
        assert d.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_not_detected_result(self, detection_not_detected):
        d = detection_not_detected
        assert d.detected is False
        assert d.failure_type == "none"

    def test_detection_has_timestamp(self, detection_job_failure):
        assert detection_job_failure.detected_at is not None
        assert isinstance(detection_job_failure.detected_at, datetime)

    def test_detection_tracks_affected_downstream(self, detection_job_failure):
        assert len(detection_job_failure.affected_downstream) > 0
        assert "transactions.gold.daily_summary" in detection_job_failure.affected_downstream

    def test_detection_records_affected(self, detection_data_corruption):
        assert detection_data_corruption.records_affected == 3

    def test_detection_details_populated(self, detection_job_failure):
        details = detection_job_failure.details
        assert "job_id" in details
        assert "run_id" in details
        assert "failed_tasks" in details

    def test_ec2_detection_fields(self, detection_ec2_failure):
        d = detection_ec2_failure
        assert d.failure_type == "ec2_instance_stop"
        assert "instance_id" in d.details
        assert d.details["current_state"] == "stopped"

    def test_s3_detection_fields(self, detection_s3_denied):
        d = detection_s3_denied
        assert d.failure_type == "s3_access_denied"
        assert d.records_affected == 5000


class TestDatabricksDetector:
    """Test Databricks-specific failure detection."""

    def test_detects_failed_job_run(self, config, mock_databricks_api):
        """Detector should identify a failed Databricks job."""
        from src.detector.databricks_detector import DatabricksFailureDetector

        detector = DatabricksFailureDetector(config)
        result = detector.detect(run_id="67890")

        assert result.detected is True
        assert result.failure_type == "databricks_job_failure"

    def test_detects_healthy_job_run(self, config, mock_databricks_api):
        """Detector should return not-detected for healthy jobs."""
        from src.detector.databricks_detector import DatabricksFailureDetector

        # Override mock to return success
        mock_databricks_api["get"].return_value.json = lambda: {
            "run_id": 67890,
            "state": {
                "life_cycle_state": "TERMINATED",
                "result_state": "SUCCESS",
                "state_message": "All tasks completed",
            },
            "tasks": [],
        }

        detector = DatabricksFailureDetector(config)
        result = detector.detect(run_id="67890")

        assert result.detected is False

    def test_identifies_failed_tasks(self, config, mock_databricks_api):
        """Detector should list which tasks failed."""
        from src.detector.databricks_detector import DatabricksFailureDetector

        detector = DatabricksFailureDetector(config)
        result = detector.detect(run_id="67890")

        assert "transform_silver" in result.details.get("failed_tasks", [])

    def test_handles_api_error_gracefully(self, config, mock_databricks_api):
        """Detector should handle API errors without crashing."""
        from src.detector.databricks_detector import DatabricksFailureDetector

        mock_databricks_api["get"].side_effect = Exception("Connection refused")

        detector = DatabricksFailureDetector(config)
        result = detector.detect(run_id="67890")

        # Should return a detection with error info, not crash
        assert result is not None

