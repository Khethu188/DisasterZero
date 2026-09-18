
"""
tests/conftest.py
─────────────────
Shared fixtures for the entire DisasterZero test suite.

Provides:
  - Mock configurations (no real AWS/Databricks needed)
  - Sample data factories
  - Reusable detection/recovery/quality gate results
  - HTTP mocking helpers
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config import (
    DisasterZeroConfig,
    DatabricksConfig,
    AWSConfig,
    S3Config,
    EC2Config,
    RTOTarget,
    RPOTarget,
    Environment,
    FailureType,
)
from src.detector.base import DetectionResult
from src.recovery.base import RecoveryResult, RecoveryAction
from src.verifier.rto_rpo import RTORPOReport
from src.datatrust_bridge.quality_gate import (
    QualityGateResult,
    QualityCheckResult,
    QualityRule,
    QualityStatus,
    CheckType,
)


# ═══════════════════════════════════════════════════════════════
# Configuration Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def config():
    """Minimal test configuration — no real credentials needed."""
    return DisasterZeroConfig(
        environment=Environment.DEV,
        databricks=DatabricksConfig(
            host="https://test-workspace.cloud.databricks.com",
            token="dapi_test_token_000000",
            warehouse_id="test-warehouse-id",
            job_id="12345",
            cluster_id="0918-test-cluster",
        ),
        aws=AWSConfig(
            region="af-south-1",
            account_id="123456789012",
        ),
        s3=S3Config(
            bucket_name="disasterzero-test-bucket",
        ),
        ec2=EC2Config(
            instance_id="i-0test123instance",
        ),
        rto=RTOTarget(
            target_seconds=600,
        ),
        rpo=RPOTarget(
            target_records=0,
            target_seconds=60,
        ),
    )


@pytest.fixture
def prod_config(config):
    """Production-like config with stricter targets."""
    config.environment = Environment.PROD
    config.rto.target_seconds = 300
    config.rpo.target_records = 0
    config.rpo.target_seconds = 30
    return config


# ═══════════════════════════════════════════════════════════════
# Time Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def now():
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


@pytest.fixture
def timestamps(now):
    """Standard incident timeline timestamps."""
    return {
        "injected": now - timedelta(seconds=50),
        "detected": now - timedelta(seconds=48),
        "recovery_start": now - timedelta(seconds=46),
        "recovery_end": now - timedelta(seconds=5),
        "verified": now,
    }


# ═══════════════════════════════════════════════════════════════
# Detection Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def detection_job_failure(timestamps):
    """Detection result for a Databricks job failure."""
    return DetectionResult(
        detected=True,
        failure_type="databricks_job_failure",
        target="job:12345/run:67890",
        details={
            "job_id": "12345",
            "run_id": "67890",
            "job_name": "transaction-pipeline",
            "state": "INTERNAL_ERROR",
            "failed_tasks": ["transform_silver"],
            "state_message": "Task failed with exception",
        },
        detected_at=timestamps["detected"],
        affected_downstream=[
            "transactions.gold.daily_summary",
            "transactions.gold.risk_scores",
        ],
        records_affected=18420,
        severity="HIGH",
    )


@pytest.fixture
def detection_data_corruption(timestamps):
    """Detection result for data corruption."""
    return DetectionResult(
        detected=True,
        failure_type="data_corruption",
        target="transactions.silver.processed",
        details={
            "corrupt_records": 3,
            "null_fields": ["amount", "currency"],
            "invalid_values": {"amount": [-999]},
        },
        detected_at=timestamps["detected"],
        affected_downstream=["transactions.gold.daily_summary"],
        records_affected=3,
        severity="CRITICAL",
    )


@pytest.fixture
def detection_ec2_failure(timestamps):
    """Detection result for EC2 instance failure."""
    return DetectionResult(
        detected=True,
        failure_type="ec2_instance_stop",
        target="ec2:i-0test123instance",
        details={
            "instance_id": "i-0test123instance",
            "previous_state": "running",
            "current_state": "stopped",
        },
        detected_at=timestamps["detected"],
        affected_downstream=[],
        records_affected=0,
        severity="HIGH",
    )


@pytest.fixture
def detection_s3_denied(timestamps):
    """Detection result for S3 access denial."""
    return DetectionResult(
        detected=True,
        failure_type="s3_access_denied",
        target="s3:disasterzero-test-bucket",
        details={
            "bucket": "disasterzero-test-bucket",
            "error": "AccessDenied",
        },
        detected_at=timestamps["detected"],
        affected_downstream=["transactions.bronze.raw_transactions"],
        records_affected=5000,
        severity="HIGH",
    )


@pytest.fixture
def detection_not_detected():
    """Detection result when no failure is found."""
    return DetectionResult(
        detected=False,
        failure_type="none",
        target="",
        details={},
    )


# ═══════════════════════════════════════════════════════════════
# Recovery Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def recovery_success(detection_job_failure, timestamps):
    """Successful recovery result."""
    return RecoveryResult(
        detection=detection_job_failure,
        actions=[
            RecoveryAction(
                action="quarantine_corrupt_records",
                target="transactions.silver.processed",
                started_at=timestamps["recovery_start"],
                completed_at=timestamps["recovery_start"] + timedelta(seconds=12),
                success=True,
                duration_seconds=12.0,
                details={"records_quarantined": 3},
            ),
            RecoveryAction(
                action="repair_run",
                target="job:12345/run:67890",
                started_at=timestamps["recovery_start"] + timedelta(seconds=12),
                completed_at=timestamps["recovery_end"],
                success=True,
                duration_seconds=29.0,
                details={"new_run_id": "99999"},
            ),
        ],
        recovered=True,
        recovery_start=timestamps["recovery_start"],
        recovery_end=timestamps["recovery_end"],
        total_duration_seconds=41.0,
        records_recovered=18420,
        records_lost=0,
        data_consistent=True,
    )


@pytest.fixture
def recovery_partial(detection_s3_denied, timestamps):
    """Partial recovery — some records lost."""
    return RecoveryResult(
        detection=detection_s3_denied,
        actions=[
            RecoveryAction(
                action="restore_bucket_policy",
                target="s3:disasterzero-test-bucket",
                started_at=timestamps["recovery_start"],
                completed_at=timestamps["recovery_start"] + timedelta(seconds=5),
                success=True,
                duration_seconds=5.0,
                details={},
            ),
            RecoveryAction(
                action="rerun_ingestion",
                target="job:12345",
                started_at=timestamps["recovery_start"] + timedelta(seconds=5),
                completed_at=timestamps["recovery_end"],
                success=False,
                duration_seconds=36.0,
                details={"error": "Partial data loss during outage"},
            ),
        ],
        recovered=False,
        recovery_start=timestamps["recovery_start"],
        recovery_end=timestamps["recovery_end"],
        total_duration_seconds=41.0,
        records_recovered=4988,
        records_lost=12,
        data_consistent=False,
    )


@pytest.fixture
def recovery_failed(detection_job_failure, timestamps):
    """Completely failed recovery."""
    return RecoveryResult(
        detection=detection_job_failure,
        actions=[
            RecoveryAction(
                action="repair_run",
                target="job:12345/run:67890",
                started_at=timestamps["recovery_start"],
                completed_at=timestamps["recovery_end"],
                success=False,
                duration_seconds=41.0,
                details={"error": "Cluster terminated during recovery"},
            ),
        ],
        recovered=False,
        recovery_start=timestamps["recovery_start"],
        recovery_end=timestamps["recovery_end"],
        total_duration_seconds=41.0,
        records_recovered=0,
        records_lost=18420,
        data_consistent=False,
    )


# ═══════════════════════════════════════════════════════════════
# RTO/RPO Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def rto_rpo_passed(timestamps):
    """RTO/RPO report where all targets are met."""
    return RTORPOReport(
        incident_id="INC-TEST-001",
        failure_type="databricks_job_failure",
        target="job:12345/run:67890",
        failure_detected_at=timestamps["detected"],
        recovery_started_at=timestamps["recovery_start"],
        recovery_completed_at=timestamps["recovery_end"],
        detection_time_seconds=2.0,
        recovery_time_seconds=41.0,
        total_rto_seconds=43.0,
        rto_target_seconds=600.0,
        rto_met=True,
        records_after_recovery=18420,
        records_lost=0,
        rpo_target_records=0,
        rpo_target_seconds=60.0,
        rpo_met=True,
        fully_recovered=True,
        data_consistent=True,
        duplicates_introduced=False,
        verification_passed=True,
    )


@pytest.fixture
def rto_rpo_failed(timestamps):
    """RTO/RPO report where targets are missed."""
    return RTORPOReport(
        incident_id="INC-TEST-002",
        failure_type="s3_access_denied",
        target="s3:disasterzero-test-bucket",
        failure_detected_at=timestamps["detected"],
        recovery_started_at=timestamps["recovery_start"],
        recovery_completed_at=timestamps["recovery_end"],
        detection_time_seconds=8.0,
        recovery_time_seconds=620.0,
        total_rto_seconds=628.0,
        rto_target_seconds=600.0,
        rto_met=False,
        records_after_recovery=4988,
        records_lost=12,
        rpo_target_records=0,
        rpo_target_seconds=60.0,
        rpo_met=False,
        fully_recovered=False,
        data_consistent=False,
        duplicates_introduced=False,
        verification_passed=False,
    )


# ═══════════════════════════════════════════════════════════════
# Quality Gate Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def quality_gate_passed():
    """Quality gate result — all checks passed."""
    return QualityGateResult(
        gate_id="QG-TEST001",
        table="transactions.silver.processed",
        overall_status=QualityStatus.PASSED,
        total_checks=12,
        passed_checks=12,
        failed_checks=0,
        total_violations=0,
        records_quarantined=0,
    )


@pytest.fixture
def quality_gate_failed():
    """Quality gate result — critical failures detected."""
    return QualityGateResult(
        gate_id="QG-TEST002",
        table="transactions.silver.processed",
        overall_status=QualityStatus.CRITICAL,
        total_checks=12,
        passed_checks=9,
        failed_checks=3,
        total_violations=47,
        records_quarantined=47,
        triggered_recovery=True,
        checks=[
            QualityCheckResult(
                rule=QualityRule(
                    rule_id="SLV-001",
                    name="No NULL transaction IDs",
                    check_type=CheckType.COMPLETENESS,
                    severity="CRITICAL",
                ),
                total_records=10000,
                violation_count=15,
                violation_rate=0.0015,
                status=QualityStatus.CRITICAL,
            ),
            QualityCheckResult(
                rule=QualityRule(
                    rule_id="SLV-020",
                    name="No negative amounts",
                    check_type=CheckType.VALIDITY,
                    severity="HIGH",
                ),
                total_records=10000,
                violation_count=32,
                violation_rate=0.0032,
                status=QualityStatus.FAILED,
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════
# Mock Helpers
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def mock_databricks_api():
    """Mock Databricks REST API responses."""
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # Default job run response
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "run_id": 67890,
                "state": {
                    "life_cycle_state": "TERMINATED",
                    "result_state": "FAILED",
                    "state_message": "Task failed with exception",
                },
                "tasks": [
                    {
                        "task_key": "transform_silver",
                        "state": {
                            "life_cycle_state": "TERMINATED",
                            "result_state": "FAILED",
                        },
                    }
                ],
            },
        )

        # Default repair run response
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"repair_id": 99999},
        )

        yield {"get": mock_get, "post": mock_post}


@pytest.fixture
def mock_aws_clients():
    """Mock AWS service clients."""
    with patch("boto3.client") as mock_client:
        clients = {}

        def get_client(service, **kwargs):
            if service not in clients:
                clients[service] = MagicMock()
            return clients[service]

        mock_client.side_effect = get_client

        # Pre-configure EC2
        ec2 = get_client("ec2")
        ec2.describe_instances.return_value = {
            "Reservations": [{
                "Instances": [{
                    "InstanceId": "i-0test123instance",
                    "State": {"Name": "running"},
                }]
            }]
        }

        # Pre-configure S3
        s3 = get_client("s3")
        s3.get_bucket_policy.return_value = {
            "Policy": json.dumps({
                "Version": "2012-10-17",
                "Statement": [],
            })
        }

        yield clients


@pytest.fixture
def tmp_reports_dir(tmp_path):
    """Temporary reports directory for test output."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    return str(reports_dir)

