
"""
tests/integration/test_pipeline_flow.py
───────────────────────────────────────
Integration tests for the full pipeline flow:
  Simulate → Detect → Recover → Verify → Report
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from src.config import FailureType


class TestDetectRecoverFlow:
    """Test the detect → recover integration."""

    def test_detection_feeds_into_recovery(
        self, config, detection_job_failure, mock_databricks_api,
    ):
        """Detection result should be accepted by recovery engine."""
        from src.recovery.databricks_recovery import DatabricksRecoveryEngine

        engine = DatabricksRecoveryEngine(config)
        result = engine.recover(detection_job_failure)

        assert result is not None
        assert result.detection == detection_job_failure
        assert result.detection.failure_type == "databricks_job_failure"

    def test_recovery_feeds_into_verifier(
        self, config, recovery_success,
    ):
        """Recovery result should be accepted by RTO/RPO verifier."""
        from src.verifier.rto_rpo import RTORPOVerifier

        verifier = RTORPOVerifier(config.rto, config.rpo)
        report = verifier.measure(recovery_success)

        assert report is not None
        assert report.total_rto_seconds > 0

    def test_verifier_feeds_into_report(
        self, config, detection_job_failure, recovery_success, rto_rpo_passed,
    ):
        """RTO/RPO report should be accepted by report generator."""
        from src.reporting.report_generator import RecoveryReportGenerator

        generator = RecoveryReportGenerator(config)
        report = generator.build_incident_report(
            scenario_name="Flow Test",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )

        assert report is not None
        assert report.overall_passed is True


class TestSimulateDetectFlow:
    """Test the simulate → detect integration."""

    def test_job_failure_simulation_detectable(
        self, config, mock_databricks_api, mock_aws_clients,
    ):
        """Simulated job failure should be detectable."""
        from src.simulator.databricks_failures import DatabricksFailureSimulator
        from src.detector.databricks_detector import DatabricksFailureDetector

        simulator = DatabricksFailureSimulator(config)
        injection = simulator.inject_failure(FailureType.DATABRICKS_JOB_FAILURE)

        detector = DatabricksFailureDetector(config)
        detection = detector.detect(run_id=injection.run_id)

        assert detection.detected is True

    def test_ec2_failure_simulation_detectable(
        self, config, mock_aws_clients,
    ):
        """Simulated EC2 stop should be detectable."""
        from src.simulator.aws_failures import AWSFailureSimulator
        from src.detector.aws_detector import AWSFailureDetector

        # Configure mock: after stop, instance shows as stopped
        mock_aws_clients["ec2"].describe_instances.return_value = {
            "Reservations": [{
                "Instances": [{
                    "InstanceId": "i-0test123instance",
                    "State": {"Name": "stopped"},
                }]
            }]
        }

        simulator = AWSFailureSimulator(config)
        simulator.inject_failure(FailureType.EC2_INSTANCE_STOP)

        detector = AWSFailureDetector(config)
        detection = detector.detect_ec2(instance_id="i-0test123instance")

        assert detection.detected is True
        assert detection.failure_type == "ec2_instance_stop"


class TestRecoverVerifyFlow:
    """Test the recover → verify → quality gate integration."""

    def test_successful_recovery_passes_verification(
        self, config, recovery_success,
    ):
        """Successful recovery should pass RTO/RPO verification."""
        from src.verifier.rto_rpo import RTORPOVerifier

        verifier = RTORPOVerifier(config.rto, config.rpo)
        report = verifier.measure(recovery_success)

        assert report.rto_met is True
        assert report.rpo_met is True
        assert report.verification_passed is True

    def test_partial_recovery_fails_verification(
        self, config, recovery_partial,
    ):
        """Partial recovery should fail RPO verification."""
        from src.verifier.rto_rpo import RTORPOVerifier

        verifier = RTORPOVerifier(config.rto, config.rpo)
        report = verifier.measure(recovery_partial)

        assert report.rpo_met is False
        assert report.records_lost > 0

    @patch("src.datatrust_bridge.quality_gate.DataTrustQualityGate.evaluate")
    def test_recovery_followed_by_quality_gate(
        self, mock_evaluate, config, recovery_success,
    ):
        """After recovery, quality gate should verify data integrity."""
        from src.datatrust_bridge.quality_gate import (
            DataTrustQualityGate,
            QualityGateResult,
            QualityStatus,
        )

        mock_evaluate.return_value = QualityGateResult(
            overall_status=QualityStatus.PASSED,
            total_checks=12,
            passed_checks=12,
            failed_checks=0,
        )

        gate = DataTrustQualityGate(config)
        result = gate.evaluate("transactions.silver.processed")

        assert result.overall_status == QualityStatus.PASSED
        assert result.failed_checks == 0


class TestFullPipelineFlow:
    """Test the complete pipeline: Simulate → Detect → Recover → Verify → Report."""

    def test_full_flow_job_failure(
        self, config, mock_databricks_api, mock_aws_clients, tmp_reports_dir,
    ):
        """Full end-to-end flow for a Databricks job failure."""
        from src.simulator.databricks_failures import DatabricksFailureSimulator
        from src.detector.databricks_detector import DatabricksFailureDetector
        from src.recovery.databricks_recovery import DatabricksRecoveryEngine
        from src.verifier.rto_rpo import RTORPOVerifier
        from src.reporting.report_generator import RecoveryReportGenerator

        # 1. Simulate
        simulator = DatabricksFailureSimulator(config)
        injection = simulator.inject_failure(FailureType.DATABRICKS_JOB_FAILURE)

        # 2. Detect
        detector = DatabricksFailureDetector(config)
        detection = detector.detect(run_id=injection.run_id)
        assert detection.detected is True

        # 3. Recover
        engine = DatabricksRecoveryEngine(config)
        recovery = engine.recover(detection)
        assert recovery is not None

        # 4. Verify
        verifier = RTORPOVerifier(config.rto, config.rpo)
        rto_rpo = verifier.measure(recovery)
        assert rto_rpo is not None

        # 5. Report
        generator = RecoveryReportGenerator(config)
        generator.reports_dir = tmp_reports_dir
        report = generator.build_incident_report(
            scenario_name="Full Flow — Job Failure",
            detection=detection,
            recovery=recovery,
            rto_rpo=rto_rpo,
        )

        assert report is not None
        assert report.incident_id.startswith("INC-")

        # 6. Cleanup
        simulator.cleanup(injection)

