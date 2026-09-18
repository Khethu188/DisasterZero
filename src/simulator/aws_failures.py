
"""
src/simulator/aws_failures.py
─────────────────────────────
Simulates AWS failures: EC2 instance stop, S3 access denial.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3

from src.config import DisasterZeroConfig, FailureType
from src.simulator.databricks_failures import InjectionResult


class AWSFailureSimulator:
    """Inject failures into AWS infrastructure."""

    def __init__(self, config: DisasterZeroConfig):
        self.config = config
        self.ec2 = boto3.client("ec2", region_name=config.aws.region)
        self.s3 = boto3.client("s3", region_name=config.aws.region)

    def inject_failure(self, failure_type: FailureType, **kwargs) -> InjectionResult:
        """Inject a specific AWS failure type."""
        handlers = {
            FailureType.EC2_INSTANCE_STOP: self._inject_ec2_stop,
            FailureType.S3_ACCESS_DENIED: self._inject_s3_deny,
        }

        handler = handlers.get(failure_type)
        if handler is None:
            raise ValueError(f"Unsupported failure type for AWS: {failure_type}")

        return handler(**kwargs)

    def cleanup(self, injection: InjectionResult) -> None:
        """Reverse the injected failure."""
        cleanup_handlers = {
            FailureType.EC2_INSTANCE_STOP: self._cleanup_ec2,
            FailureType.S3_ACCESS_DENIED: self._cleanup_s3,
        }

        handler = cleanup_handlers.get(injection.failure_type)
        if handler:
            handler(injection)

    # ── Injection Methods ──

    def _inject_ec2_stop(self, **kwargs) -> InjectionResult:
        """Stop an EC2 instance to simulate failure."""
        instance_id = self.config.ec2.instance_id

        # Save current state for cleanup
        resp = self.ec2.describe_instances(InstanceIds=[instance_id])
        current_state = resp["Reservations"][0]["Instances"][0]["State"]["Name"]

        self.ec2.stop_instances(InstanceIds=[instance_id])

        return InjectionResult(
            failure_type=FailureType.EC2_INSTANCE_STOP,
            target=f"ec2:{instance_id}",
            details={
                "instance_id": instance_id,
                "previous_state": current_state,
                "action": "stop_instance",
            },
            cleanup_info={
                "instance_id": instance_id,
                "previous_state": current_state,
            },
        )

    def _inject_s3_deny(self, **kwargs) -> InjectionResult:
        """Apply a deny-all bucket policy to simulate access failure."""
        bucket = self.config.s3.bucket_name

        # Save existing policy for cleanup
        try:
            existing = self.s3.get_bucket_policy(Bucket=bucket)
            original_policy = existing["Policy"]
        except self.s3.exceptions.from_code("NoSuchBucketPolicy"):
            original_policy = None
        except Exception:
            original_policy = None

        # Apply deny policy
        deny_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DisasterZeroDenyAll",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [
                        f"arn:aws:s3:::{bucket}",
                        f"arn:aws:s3:::{bucket}/*",
                    ],
                    "Condition": {
                        "StringNotEquals": {
                            "aws:PrincipalAccount": self.config.aws.account_id
                        }
                    },
                }
            ],
        }

        self.s3.put_bucket_policy(
            Bucket=bucket,
            Policy=json.dumps(deny_policy),
        )

        return InjectionResult(
            failure_type=FailureType.S3_ACCESS_DENIED,
            target=f"s3:{bucket}",
            details={
                "bucket": bucket,
                "action": "apply_deny_policy",
            },
            cleanup_info={
                "bucket": bucket,
                "original_policy": original_policy,
            },
        )

    # ── Cleanup Methods ──

    def _cleanup_ec2(self, injection: InjectionResult) -> None:
        """Restart the stopped EC2 instance."""
        instance_id = injection.cleanup_info.get("instance_id")
        if instance_id:
            self.ec2.start_instances(InstanceIds=[instance_id])

    def _cleanup_s3(self, injection: InjectionResult) -> None:
        """Restore the original S3 bucket policy."""
        bucket = injection.cleanup_info.get("bucket")
        original_policy = injection.cleanup_info.get("original_policy")

        if bucket:
            if original_policy:
                self.s3.put_bucket_policy(Bucket=bucket, Policy=original_policy)
            else:
                self.s3.delete_bucket_policy(Bucket=bucket)

