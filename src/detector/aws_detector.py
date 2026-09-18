
"""
src/detector/aws_detector.py
────────────────────────────
Detects failures in AWS services (EC2, S3).
"""

import json
from datetime import datetime, timezone
from typing import Optional

import boto3

from src.config import DisasterZeroConfig
from src.detector.base import DetectionResult


class AWSFailureDetector:
    """Detect AWS infrastructure failures."""

    def __init__(self, config: DisasterZeroConfig):
        self.config = config
        self.ec2 = boto3.client("ec2", region_name=config.aws.region)
        self.s3 = boto3.client("s3", region_name=config.aws.region)

    def detect_ec2(self, instance_id: Optional[str] = None) -> DetectionResult:
        """Check if an EC2 instance is stopped or impaired."""
        iid = instance_id or self.config.ec2.instance_id
        try:
            resp = self.ec2.describe_instances(InstanceIds=[iid])
            instance = resp["Reservations"][0]["Instances"][0]
            state = instance["State"]["Name"]

            if state in ("stopped", "terminated", "shutting-down"):
                return DetectionResult(
                    detected=True,
                    failure_type="ec2_instance_stop",
                    target=f"ec2:{iid}",
                    details={
                        "instance_id": iid,
                        "previous_state": "running",
                        "current_state": state,
                        "instance_type": instance.get("InstanceType", ""),
                    },
                    severity="HIGH",
                )

            return DetectionResult(detected=False, failure_type="none")

        except Exception as e:
            return DetectionResult(
                detected=True,
                failure_type="ec2_api_error",
                target=f"ec2:{iid}",
                details={"error": str(e)},
                severity="HIGH",
            )

    def detect_s3(self, bucket: Optional[str] = None) -> DetectionResult:
        """Check if S3 bucket is accessible."""
        bucket_name = bucket or self.config.s3.bucket_name
        try:
            self.s3.head_bucket(Bucket=bucket_name)

            # Also try to list objects
            self.s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)

            return DetectionResult(detected=False, failure_type="none")

        except self.s3.exceptions.ClientError as e:
            error_code = e.response["Error"]["Code"]
            return DetectionResult(
                detected=True,
                failure_type="s3_access_denied",
                target=f"s3:{bucket_name}",
                details={
                    "bucket": bucket_name,
                    "error": error_code,
                    "message": str(e),
                },
                affected_downstream=[self.config.databricks.bronze_table],
                records_affected=5000,
                severity="HIGH",
            )

        except Exception as e:
            return DetectionResult(
                detected=True,
                failure_type="s3_api_error",
                target=f"s3:{bucket_name}",
                details={"error": str(e)},
                severity="HIGH",
            )

