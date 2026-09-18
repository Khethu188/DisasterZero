
"""
src/recovery/aws_recovery.py
────────────────────────────
Automated recovery for AWS failures: EC2 restart, S3 policy restore.
"""

import json
import time
from datetime import datetime, timezone

import boto3

from src.config import DisasterZeroConfig
from src.detector.base import DetectionResult
from src.recovery.base import RecoveryResult, RecoveryAction


class AWSRecoveryEngine:
    """Recover from AWS infrastructure failures."""

    def __init__(self, config: DisasterZeroConfig):
        self.config = config
        self.ec2 = boto3.client("ec2", region_name=config.aws.region)
        self.s3 = boto3.client("s3", region_name=config.aws.region)

    def recover(self, detection: DetectionResult) -> RecoveryResult:
        """Execute recovery based on detected failure type."""
        recovery_start = datetime.now(timezone.utc)
        actions = []

        try:
            if detection.failure_type == "ec2_instance_stop":
                actions = self._recover_ec2(detection)
            elif detection.failure_type == "s3_access_denied":
                actions = self._recover_s3(detection)
            else:
                actions = [RecoveryAction(
                    action="unknown_failure_type",
                    target=detection.target,
                    started_at=recovery_start,
                    completed_at=datetime.now(timezone.utc),
                    success=False,
                )]
        except Exception as e:
            actions.append(RecoveryAction(
                action="recovery_error",
                target=detection.target,
                started_at=recovery_start,
                completed_at=datetime.now(timezone.utc),
                success=False,
                details={"error": str(e)},
            ))

        recovery_end = datetime.now(timezone.utc)
        all_success = all(a.success for a in actions) if actions else False

        return RecoveryResult(
            detection=detection,
            actions=actions,
            recovered=all_success,
            recovery_start=recovery_start,
            recovery_end=recovery_end,
            total_duration_seconds=(recovery_end - recovery_start).total_seconds(),
            records_recovered=detection.records_affected if all_success else 0,
            records_lost=0 if all_success else detection.records_affected,
            data_consistent=all_success,
        )

    def _recover_ec2(self, detection: DetectionResult) -> list:
        """Restart a stopped EC2 instance."""
        instance_id = detection.details.get("instance_id", self.config.ec2.instance_id)
        action_start = datetime.now(timezone.utc)

        try:
            self.ec2.start_instances(InstanceIds=[instance_id])

            # Wait for running state
            waiter = self.ec2.get_waiter("instance_running")
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={"Delay": 5, "MaxAttempts": 60},
            )

            action_end = datetime.now(timezone.utc)
            return [RecoveryAction(
                action="restart_ec2_instance",
                target=f"ec2:{instance_id}",
                started_at=action_start,
                completed_at=action_end,
                success=True,
                duration_seconds=(action_end - action_start).total_seconds(),
                details={"instance_id": instance_id, "new_state": "running"},
            )]

        except Exception as e:
            action_end = datetime.now(timezone.utc)
            return [RecoveryAction(
                action="restart_ec2_instance",
                target=f"ec2:{instance_id}",
                started_at=action_start,
                completed_at=action_end,
                success=False,
                duration_seconds=(action_end - action_start).total_seconds(),
                details={"error": str(e)},
            )]

    def _recover_s3(self, detection: DetectionResult) -> list:
        """Remove deny policy from S3 bucket."""
        bucket = detection.details.get("bucket", self.config.s3.bucket_name)
        action_start = datetime.now(timezone.utc)

        try:
            # Get current policy
            try:
                resp = self.s3.get_bucket_policy(Bucket=bucket)
                policy = json.loads(resp["Policy"])
            except Exception:
                policy = {"Version": "2012-10-17", "Statement": []}

            # Remove DisasterZero deny statements
            cleaned = [
                stmt for stmt in policy.get("Statement", [])
                if stmt.get("Sid") != "DisasterZeroDenyAll"
            ]

            if cleaned:
                policy["Statement"] = cleaned
                self.s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
            else:
                self.s3.delete_bucket_policy(Bucket=bucket)

            action_end = datetime.now(timezone.utc)
            return [RecoveryAction(
                action="restore_bucket_policy",
                target=f"s3:{bucket}",
                started_at=action_start,
                completed_at=action_end,
                success=True,
                duration_seconds=(action_end - action_start).total_seconds(),
                details={"bucket": bucket, "statements_removed": 1},
            )]

        except Exception as e:
            action_end = datetime.now(timezone.utc)
            return [RecoveryAction(
                action="restore_bucket_policy",
                target=f"s3:{bucket}",
                started_at=action_start,
                completed_at=action_end,
                success=False,
                duration_seconds=(action_end - action_start).total_seconds(),
                details={"error": str(e)},
            )]

