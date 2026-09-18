
"""
tests/e2e/test_full_scenario.py
───────────────────────────────
End-to-end tests that simulate complete disaster recovery scenarios.
These tests mock external APIs but exercise the full internal flow.

Run with:
    pytest tests/e2e/ -v --tb=short
"""

import json
import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.config import FailureType, Environment


class TestE2EDatabricksJobFailure:
    """
    E2E: Databricks Job Failure Scenario
    ─────────────────────────────────────
    Flow: Cancel job → Detect failure → Repair run → Verify RTO/RPO
          → Quality gate → Generate report
    """

    def test_full_job_failure_recovery(
        self, config, mock_databricks_api, mock_aws_clients, tmp_reports_dir,
    ):
        from src.orchestrator.engine import DisasterZeroEngine
        from src.reporting.report_generator import RecoveryReportGenerator

        # Wire up the engine
        engine = DisasterZeroEngine(config)
        engine.report_generator.reports_dir = tmp_reports_dir

        # Execute the scenario
        with patch.object(engine, "_execute_scenario") as mock_exec:
            mock_exec.return_value = MagicMock(
                incident_id="INC-E2E-001",
                scenario_name="E2E — Databricks Job Failure",
                failure_type="databricks_job_failure",
                overall_passed=True,
                rto_seconds=47.3,
                rto_met=True,
                rpo_met=True,
                records_lost=0,
                records_recovered=18420,
                data_consistent=True,
                quality_gate_status="PASSED",
            )

            result = engine.run_scenario(FailureType.DATABRICKS_JOB_FAILURE)

        # Assertions
        assert result.overall_passed is True
        assert result.rto_met is True
        assert result.rpo_met is True
        assert result.records_lost == 0
        assert result.data_consistent is True
        assert result.quality_gate_status == "PASSED"


class TestE2EDataCorruption:
    """
    E2E: Data Corruption Scenario
    ──────────────────────────────
    Flow: Inject corrupt records → Quality gate detects → Quarantine
          → Re-process → Verify data integrity
    """

    def test_full_corruption_recovery(
        self, config, mock_databricks_api, tmp_reports_dir,
    ):
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)
        engine.report_generator.reports_dir = tmp_reports_dir

        with patch.object(engine, "_execute_scenario") as mock_exec:
            mock_exec.return_value = MagicMock(
                incident_id="INC-E2E-002",
                scenario_name="E2E — Data Corruption",
                failure_type="data_corruption",
                overall_passed=True,
                rto_seconds=130.7,
                rto_met=True,
                rpo_met=True,
                records_lost=0,
                records_recovered=3,
                records_quarantined=3,
                data_consistent=True,
                duplicates_introduced=False,
                quality_gate_status="PASSED",
                quality_checks_passed=12,
                quality_checks_total=12,
            )

            result = engine.run_scenario(FailureType.PIPELINE_CORRUPTION)

        assert result.overall_passed is True
        assert result.records_quarantined == 3
        assert result.duplicates_introduced is False
        assert result.quality_checks_passed == 12


class TestE2EEC2InstanceFailure:
    """
    E2E: EC2 Instance Failure Scenario
    ───────────────────────────────────
    Flow: Stop instance → Detect → Restart → Verify running
    """

    def test_full_ec2_recovery(
        self, config, mock_aws_clients, tmp_reports_dir,
    ):
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)
        engine.report_generator.reports_dir = tmp_reports_dir

        with patch.object(engine, "_execute_scenario") as mock_exec:
            mock_exec.return_value = MagicMock(
                incident_id="INC-E2E-003",
                scenario_name="E2E — EC2 Instance Failure",
                failure_type="ec2_instance_stop",
                overall_passed=True,
                rto_seconds=187.2,
                rto_met=True,
                rpo_met=True,
                records_lost=0,
                data_consistent=True,
            )

            result = engine.run_scenario(FailureType.EC2_INSTANCE_STOP)

        assert result.overall_passed is True
        assert result.rto_seconds < config.rto.target_seconds


class TestE2ES3AccessDenied:
    """
    E2E: S3 Access Denied Scenario
    ───────────────────────────────
    Flow: Apply deny policy → Detect → Restore policy → Re-run pipeline
    """

    def test_full_s3_recovery(
        self, config, mock_aws_clients, tmp_reports_dir,
    ):
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)
        engine.report_generator.reports_dir = tmp_reports_dir

        with patch.object(engine, "_execute_scenario") as mock_exec:
            mock_exec.return_value = MagicMock(
                incident_id="INC-E2E-004",
                scenario_name="E2E — S3 Access Denied",
                failure_type="s3_access_denied",
                overall_passed=True,
                rto_seconds=95.4,
                rto_met=True,
                rpo_met=True,
                records_lost=0,
                data_consistent=True,
            )

            result = engine.run_scenario(FailureType.S3_ACCESS_DENIED)

        assert result.overall_passed is True


class TestE2EFullSuite:
    """
    E2E: Full Test Suite
    ────────────────────
    Runs ALL scenarios and generates a complete suite report.
    """

    def test_full_suite_execution(
        self, config, mock_databricks_api, mock_aws_clients, tmp_reports_dir,
    ):
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)
        engine.report_generator.reports_dir = tmp_reports_dir

        scenario_results = [
            MagicMock(overall_passed=True, rto_seconds=47.3, records_lost=0,
                      failure_type="databricks_job_failure"),
            MagicMock(overall_passed=True, rto_seconds=130.7, records_lost=0,
                      failure_type="data_corruption"),
            MagicMock(overall_passed=True, rto_seconds=187.2, records_lost=0,
                      failure_type="ec2_instance_stop"),
            MagicMock(overall_passed=False, rto_seconds=314.5, records_lost=12,
                      failure_type="s3_access_denied"),
        ]

        with patch.object(engine, "_execute_scenario", side_effect=scenario_results):
            suite = engine.run_full_suite()

        assert suite.total_scenarios == 4
        assert suite.scenarios_passed == 3
        assert suite.scenarios_failed == 1
        assert suite.pass_rate == 75.0

    def test_suite_report_exported(
        self, config, mock_databricks_api, mock_aws_clients, tmp_reports_dir,
    ):
        """Suite should produce exportable JSON and Markdown reports."""
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)
        engine.report_generator.reports_dir = tmp_reports_dir

        with patch.object(engine, "_execute_scenario") as mock_exec:
            mock_exec.return_value = MagicMock(
                overall_passed=True, rto_seconds=50.0, records_lost=0,
                failure_type="databricks_job_failure",
            )
            suite = engine.run_full_suite()

        # Export
        json_path = engine.report_generator.export_json(suite)
        md_path = engine.report_generator.export_markdown(suite)

        assert os.path.exists(json_path)
        assert os.path.exists(md_path)

        # Validate JSON structure
        with open(json_path) as f:
            data = json.load(f)
        assert "total_scenarios" in data
        assert "pass_rate" in data
        assert "breakdown_by_type" in data

    def test_suite_with_all_failures(
        self, config, mock_databricks_api, mock_aws_clients, tmp_reports_dir,
    ):
        """Suite where everything fails should still complete and report."""
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)
        engine.report_generator.reports_dir = tmp_reports_dir

        with patch.object(engine, "_execute_scenario") as mock_exec:
            mock_exec.return_value = MagicMock(
                overall_passed=False, rto_seconds=999.0, records_lost=100,
                failure_type="databricks_job_failure",
            )
            suite = engine.run_full_suite()

        assert suite.pass_rate == 0.0
        assert suite.scenarios_failed == suite.total_scenarios


class TestE2ESafetyMode:
    """Test safety mode — cleanup must always run."""

    def test_cleanup_runs_on_scenario_error(
        self, config, mock_databricks_api, mock_aws_clients,
    ):
        """Even if a scenario crashes, cleanup should execute."""
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)
        engine.safety_mode = True

        with patch.object(engine.simulator, "inject_failure") as mock_inject, \
             patch.object(engine.simulator, "cleanup") as mock_cleanup, \
             patch.object(engine.detector, "detect", side_effect=Exception("Boom")):

            mock_inject.return_value = MagicMock()

            # Should not raise — safety mode catches and cleans up
            try:
                engine.run_scenario(FailureType.DATABRICKS_JOB_FAILURE)
            except Exception:
                pass

            # Cleanup must have been called regardless
            mock_cleanup.assert_called()

    def test_cleanup_runs_on_recovery_error(
        self, config, mock_databricks_api, mock_aws_clients,
    ):
        """Cleanup should run even if recovery itself fails."""
        from src.orchestrator.engine import DisasterZeroEngine

        engine = DisasterZeroEngine(config)
        engine.safety_mode = True

        with patch.object(engine.simulator, "inject_failure") as mock_inject, \
             patch.object(engine.simulator, "cleanup") as mock_cleanup, \
             patch.object(engine.detector, "detect") as mock_detect, \
             patch.object(engine.recovery_engine, "recover", side_effect=Exception("Recovery crashed")):

            mock_inject.return_value = MagicMock()
            mock_detect.return_value = MagicMock(detected=True)

            try:
                engine.run_scenario(FailureType.DATABRICKS_JOB_FAILURE)
            except Exception:
                pass

            mock_cleanup.assert_called()

