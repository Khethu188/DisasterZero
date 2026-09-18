
"""
tests/unit/test_report_generator.py
────────────────────────────────────
Tests for the recovery report generator.
"""

import json
import os
import pytest

from src.reporting.report_generator import (
    RecoveryReportGenerator,
    IncidentReport,
    SuiteReport,
    IncidentTimeline,
    ReportFormat,
)


class TestIncidentReport:
    """Test incident report building."""

    def test_build_incident_report(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed, quality_gate_passed, timestamps,
    ):
        generator = RecoveryReportGenerator(config)
        report = generator.build_incident_report(
            scenario_name="Test Scenario",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
            quality_gate=quality_gate_passed,
            failure_injected_at=timestamps["injected"],
        )

        assert isinstance(report, IncidentReport)
        assert report.scenario_name == "Test Scenario"
        assert report.overall_passed is True
        assert report.rto_met is True
        assert report.rpo_met is True

    def test_incident_report_has_timeline(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed, timestamps,
    ):
        generator = RecoveryReportGenerator(config)
        report = generator.build_incident_report(
            scenario_name="Timeline Test",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
            failure_injected_at=timestamps["injected"],
        )

        assert report.timeline.failure_injected_at is not None
        assert report.timeline.failure_detected_at is not None
        assert report.timeline.recovery_started_at is not None
        assert report.timeline.total_incident_seconds > 0

    def test_incident_report_records_actions(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed,
    ):
        generator = RecoveryReportGenerator(config)
        report = generator.build_incident_report(
            scenario_name="Actions Test",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )

        assert len(report.recovery_actions) == 2
        assert report.recovery_actions[0]["success"] is True

    def test_failed_incident_report(
        self, config, detection_s3_denied, recovery_partial,
        rto_rpo_failed, quality_gate_failed,
    ):
        generator = RecoveryReportGenerator(config)
        report = generator.build_incident_report(
            scenario_name="Failed Scenario",
            detection=detection_s3_denied,
            recovery=recovery_partial,
            rto_rpo=rto_rpo_failed,
            quality_gate=quality_gate_failed,
        )

        assert report.overall_passed is False
        assert report.records_lost > 0
        assert report.quality_gate_status == "CRITICAL"

    def test_quality_gate_info_included(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed, quality_gate_passed,
    ):
        generator = RecoveryReportGenerator(config)
        report = generator.build_incident_report(
            scenario_name="QG Test",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
            quality_gate=quality_gate_passed,
        )

        assert report.quality_gate_status == "PASSED"
        assert report.quality_checks_passed == 12
        assert report.quality_checks_total == 12


class TestSuiteReport:
    """Test suite report building."""

    def test_build_suite_report(
        self, config, detection_job_failure, detection_s3_denied,
        recovery_success, recovery_partial,
        rto_rpo_passed, rto_rpo_failed,
    ):
        generator = RecoveryReportGenerator(config)

        incident1 = generator.build_incident_report(
            scenario_name="Scenario 1",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )
        incident2 = generator.build_incident_report(
            scenario_name="Scenario 2",
            detection=detection_s3_denied,
            recovery=recovery_partial,
            rto_rpo=rto_rpo_failed,
        )

        suite = generator.build_suite_report([incident1, incident2])

        assert isinstance(suite, SuiteReport)
        assert suite.total_scenarios == 2
        assert suite.scenarios_passed == 1
        assert suite.scenarios_failed == 1
        assert suite.pass_rate == 50.0

    def test_suite_rto_aggregation(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed,
    ):
        generator = RecoveryReportGenerator(config)

        incidents = []
        for i in range(3):
            inc = generator.build_incident_report(
                scenario_name=f"Scenario {i}",
                detection=detection_job_failure,
                recovery=recovery_success,
                rto_rpo=rto_rpo_passed,
            )
            incidents.append(inc)

        suite = generator.build_suite_report(incidents)

        assert suite.avg_rto_seconds > 0
        assert suite.max_rto_seconds >= suite.min_rto_seconds
        assert suite.rto_met_count == 3

    def test_suite_breakdown_by_type(
        self, config, detection_job_failure, detection_ec2_failure,
        recovery_success, rto_rpo_passed,
    ):
        generator = RecoveryReportGenerator(config)

        inc1 = generator.build_incident_report(
            scenario_name="Job Failure",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )
        inc2 = generator.build_incident_report(
            scenario_name="EC2 Failure",
            detection=detection_ec2_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )

        suite = generator.build_suite_report([inc1, inc2])

        assert "databricks_job_failure" in suite.breakdown_by_type
        assert "ec2_instance_stop" in suite.breakdown_by_type

    def test_empty_suite(self, config):
        generator = RecoveryReportGenerator(config)
        suite = generator.build_suite_report([])

        assert suite.total_scenarios == 0
        assert suite.pass_rate == 0.0


class TestReportExport:
    """Test report export to JSON and Markdown."""

    def test_export_json(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed, tmp_reports_dir,
    ):
        config_copy = config
        generator = RecoveryReportGenerator(config_copy)
        generator.reports_dir = tmp_reports_dir

        report = generator.build_incident_report(
            scenario_name="JSON Export Test",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )

        filepath = generator.export_json(report)

        assert os.path.exists(filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert data["scenario_name"] == "JSON Export Test"
        assert data["overall_passed"] is True

    def test_export_markdown(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed, tmp_reports_dir,
    ):
        generator = RecoveryReportGenerator(config)
        generator.reports_dir = tmp_reports_dir

        report = generator.build_incident_report(
            scenario_name="Markdown Export Test",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )

        filepath = generator.export_markdown(report)

        assert os.path.exists(filepath)
        content = open(filepath).read()
        assert "# DisasterZero" in content
        assert "Markdown Export Test" in content
        assert "RTO" in content
        assert "RPO" in content

    def test_export_suite_json(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed, tmp_reports_dir,
    ):
        generator = RecoveryReportGenerator(config)
        generator.reports_dir = tmp_reports_dir

        inc = generator.build_incident_report(
            scenario_name="Suite JSON Test",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )
        suite = generator.build_suite_report([inc])
        filepath = generator.export_json(suite)

        assert os.path.exists(filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert data["total_scenarios"] == 1

    def test_export_suite_markdown(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed, tmp_reports_dir,
    ):
        generator = RecoveryReportGenerator(config)
        generator.reports_dir = tmp_reports_dir

        inc = generator.build_incident_report(
            scenario_name="Suite MD Test",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )
        suite = generator.build_suite_report([inc])
        filepath = generator.export_markdown(suite)

        assert os.path.exists(filepath)
        content = open(filepath).read()
        assert "Executive Summary" in content
        assert "Breakdown by Failure Type" in content


class TestStreamlitData:
    """Test Streamlit data export."""

    def test_to_streamlit_data(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed,
    ):
        generator = RecoveryReportGenerator(config)

        inc = generator.build_incident_report(
            scenario_name="Streamlit Test",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )
        suite = generator.build_suite_report([inc])
        data = generator.to_streamlit_data(suite)

        assert "kpis" in data
        assert "rto_trend" in data
        assert "failure_breakdown" in data
        assert "incidents_table" in data
        assert "data_impact" in data

    def test_streamlit_kpis(
        self, config, detection_job_failure, recovery_success,
        rto_rpo_passed,
    ):
        generator = RecoveryReportGenerator(config)

        inc = generator.build_incident_report(
            scenario_name="KPI Test",
            detection=detection_job_failure,
            recovery=recovery_success,
            rto_rpo=rto_rpo_passed,
        )
        suite = generator.build_suite_report([inc])
        kpis = generator.to_streamlit_data(suite)["kpis"]

        assert kpis["pass_rate"] == 100.0
        assert kpis["total_scenarios"] == 1
        assert kpis["records_lost"] == 0

