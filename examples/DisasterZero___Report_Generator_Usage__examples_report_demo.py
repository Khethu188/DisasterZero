
"""
examples/report_demo.py
───────────────────────
Demonstrates report generation with sample data.
Run this to see what the reports look like without needing live infrastructure.
"""

from datetime import datetime, timedelta, timezone

from src.config import DisasterZeroConfig, RTOTarget, RPOTarget
from src.detector.base import DetectionResult
from src.recovery.base import RecoveryResult, RecoveryAction
from src.verifier.rto_rpo import RTORPOReport, RTORPOVerifier
from src.datatrust_bridge.quality_gate import QualityGateResult, QualityStatus
from src.reporting.report_generator import RecoveryReportGenerator


def create_sample_incident(
    scenario: str,
    failure_type: str,
    target: str,
    severity: str,
    rto_seconds: float,
    records_affected: int,
    records_lost: int,
    passed: bool,
) -> dict:
    """Create a realistic sample incident for demo purposes."""

    now = datetime.now(timezone.utc)
    detected_at = now - timedelta(seconds=rto_seconds + 5)
    recovery_start = detected_at + timedelta(seconds=2)
    recovery_end = recovery_start + timedelta(seconds=rto_seconds)

    detection = DetectionResult(
        detected=True,
        failure_type=failure_type,
        target=target,
        details={
            "job_id": "12345",
            "run_id": "67890",
            "job_name": "transaction-processing",
            "failed_tasks": ["transform_silver"],
            "state_message": "Task failed with exception",
        },
        detected_at=detected_at,
        affected_downstream=[
            "transactions.gold.daily_summary",
            "transactions.gold.risk_scores",
        ],
        records_affected=records_affected,
        severity=severity,
    )

    recovery = RecoveryResult(
        detection=detection,
        actions=[
            RecoveryAction(
                action="quarantine_corrupt_records",
                target=target,
                started_at=recovery_start,
                completed_at=recovery_start + timedelta(seconds=rto_seconds * 0.3),
                success=True,
                duration_seconds=rto_seconds * 0.3,
                details={"records_quarantined": records_affected},
            ),
            RecoveryAction(
                action="repair_run",
                target=f"job:12345/run:67890",
                started_at=recovery_start + timedelta(seconds=rto_seconds * 0.3),
                completed_at=recovery_end,
                success=passed,
                duration_seconds=rto_seconds * 0.7,
                details={"new_run_id": "99999", "method": "repair"},
            ),
        ],
        recovered=passed,
        recovery_start=recovery_start,
        recovery_end=recovery_end,
        total_duration_seconds=rto_seconds,
        records_recovered=records_affected - records_lost,
        records_lost=records_lost,
        data_consistent=passed,
    )

    rto_rpo = RTORPOReport(
        incident_id=f"INC-{now.strftime('%Y%m%d%H%M%S')}",
        failure_type=failure_type,
        target=target,
        failure_detected_at=detected_at,
        recovery_started_at=recovery_start,
        recovery_completed_at=recovery_end,
        detection_time_seconds=2.0,
        recovery_time_seconds=rto_seconds,
        total_rto_seconds=rto_seconds + 2.0,
        rto_target_seconds=600.0,
        rto_met=(rto_seconds + 2.0) <= 600.0,
        records_after_recovery=records_affected - records_lost,
        records_lost=records_lost,
        rpo_target_records=0,
        rpo_target_seconds=60.0,
        rpo_met=records_lost == 0,
        fully_recovered=passed,
        data_consistent=passed,
        duplicates_introduced=False,
        verification_passed=passed and records_lost == 0,
    )

    quality_gate = QualityGateResult(
        table=target,
        overall_status=QualityStatus.PASSED if passed else QualityStatus.FAILED,
        total_checks=12,
        passed_checks=12 if passed else 9,
        failed_checks=0 if passed else 3,
        total_violations=0 if passed else records_affected,
        records_quarantined=records_affected if not passed else 0,
    )

    return {
        "scenario": scenario,
        "detection": detection,
        "recovery": recovery,
        "rto_rpo": rto_rpo,
        "quality_gate": quality_gate,
        "injected_at": detected_at - timedelta(seconds=5),
    }


def main():
    config = DisasterZeroConfig()
    generator = RecoveryReportGenerator(config)

    # ── Create sample incidents ──
    samples = [
        create_sample_incident(
            scenario="Databricks Job Failure — Transaction Processing",
            failure_type="databricks_job_failure",
            target="job:12345/run:67890",
            severity="HIGH",
            rto_seconds=45.3,
            records_affected=18420,
            records_lost=0,
            passed=True,
        ),
        create_sample_incident(
            scenario="Data Corruption — Corrupt Records Injected",
            failure_type="data_corruption",
            target="transactions.silver.processed",
            severity="CRITICAL",
            rto_seconds=128.7,
            records_affected=3,
            records_lost=0,
            passed=True,
        ),
        create_sample_incident(
            scenario="EC2 Instance Failure — App Server",
            failure_type="ec2_instance_stop",
            target="ec2:i-0abc123def456",
            severity="HIGH",
            rto_seconds=187.2,
            records_affected=0,
            records_lost=0,
            passed=True,
        ),
        create_sample_incident(
            scenario="S3 Access Denied — Raw Data Bucket",
            failure_type="s3_access_denied",
            target="s3:disasterzero-data",
            severity="HIGH",
            rto_seconds=312.5,
            records_affected=5000,
            records_lost=12,
            passed=False,
        ),
    ]

    # ── Build individual incident reports ──
    incident_reports = []
    for sample in samples:
        report = generator.build_incident_report(
            scenario_name=sample["scenario"],
            detection=sample["detection"],
            recovery=sample["recovery"],
            rto_rpo=sample["rto_rpo"],
            quality_gate=sample["quality_gate"],
            failure_injected_at=sample["injected_at"],
        )
        incident_reports.append(report)

        # Export individual report
        md_path = generator.export_markdown(report)
        json_path = generator.export_json(report)
        print(f"  → {report.incident_id}: {md_path}, {json_path}")

    # ── Build suite report ──
    suite = generator.build_suite_report(
        incidents=incident_reports,
        suite_name="DisasterZero Full Test Suite — September 2026",
    )

    suite_md = generator.export_markdown(suite)
    suite_json = generator.export_json(suite)
    print(f"\nSuite report: {suite_md}, {suite_json}")

    # ── Streamlit data ──
    streamlit_data = generator.to_streamlit_data(suite)
    print(f"\nStreamlit KPIs: {streamlit_data['kpis']}")

    # ── Print a preview ──
    print(f"\n{'='*60}")
    print(f"SUITE: {suite.suite_name}")
    print(f"{'='*60}")
    print(f"Pass Rate:    {suite.pass_rate}%")
    print(f"Avg RTO:      {suite.avg_rto_seconds}s")
    print(f"Max RTO:      {suite.max_rto_seconds}s")
    print(f"Records Lost: {suite.total_records_lost}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

