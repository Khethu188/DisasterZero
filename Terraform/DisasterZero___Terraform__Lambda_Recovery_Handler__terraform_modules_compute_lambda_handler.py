
"""
terraform/modules/compute/lambda/handler.py
────────────────────────────────────────────
Lambda function for automated recovery actions.
Triggered by CloudWatch alarms via SNS.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.client("ec2")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT = os.environ.get("PROJECT", "disasterzero")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "")
APP_INSTANCE_ID = os.environ.get("APP_INSTANCE_ID", "")


def lambda_handler(event, context):
    """
    Main handler — routes recovery based on alarm type.

    Expected event from SNS → CloudWatch Alarm:
    {
        "Records": [{
            "Sns": {
                "Message": "{\"AlarmName\": \"...\", \"NewStateValue\": \"ALARM\", ...}"
            }
        }]
    }
    """
    logger.info(f"Recovery Lambda triggered: {json.dumps(event)}")

    try:
        # Parse SNS → CloudWatch alarm
        for record in event.get("Records", []):
            message = json.loads(record["Sns"]["Message"])
            alarm_name = message.get("AlarmName", "")
            new_state = message.get("NewStateValue", "")

            if new_state != "ALARM":
                logger.info(f"Ignoring non-ALARM state: {new_state}")
                continue

            logger.info(f"Processing alarm: {alarm_name}")

            # Route to appropriate recovery action
            if "ec2" in alarm_name.lower() or "instance" in alarm_name.lower():
                result = recover_ec2_instance(alarm_name, message)
            elif "s3" in alarm_name.lower() or "bucket" in alarm_name.lower():
                result = recover_s3_access(alarm_name, message)
            elif "lambda" in alarm_name.lower():
                result = handle_lambda_alarm(alarm_name, message)
            else:
                result = {
                    "action": "unknown",
                    "status": "skipped",
                    "reason": f"No recovery handler for alarm: {alarm_name}",
                }

            # Log incident
            log_incident(alarm_name, result)

            return {
                "statusCode": 200,
                "body": json.dumps(result),
            }

    except Exception as e:
        logger.error(f"Recovery failed: {e}")
        log_incident("error", {"action": "recovery_error", "error": str(e)})
        raise


def recover_ec2_instance(alarm_name: str, alarm_data: dict) -> dict:
    """Restart a stopped/failed EC2 instance."""
    instance_id = APP_INSTANCE_ID
    logger.info(f"Recovering EC2 instance: {instance_id}")

    try:
        # Check current state
        response = ec2.describe_instances(InstanceIds=[instance_id])
        state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
        logger.info(f"Instance {instance_id} current state: {state}")

        if state == "stopped":
            ec2.start_instances(InstanceIds=[instance_id])
            logger.info(f"Started instance {instance_id}")

            # Wait for running
            waiter = ec2.get_waiter("instance_running")
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={"Delay": 10, "MaxAttempts": 30},
            )

            return {
                "action": "ec2_restart",
                "instance_id": instance_id,
                "previous_state": state,
                "new_state": "running",
                "status": "success",
            }

        elif state == "running":
            return {
                "action": "ec2_restart",
                "instance_id": instance_id,
                "status": "already_running",
            }

        else:
            return {
                "action": "ec2_restart",
                "instance_id": instance_id,
                "status": "unexpected_state",
                "state": state,
            }

    except Exception as e:
        logger.error(f"EC2 recovery failed: {e}")
        return {"action": "ec2_restart", "status": "failed", "error": str(e)}


def recover_s3_access(alarm_name: str, alarm_data: dict) -> dict:
    """Restore S3 bucket policy after access denial."""
    logger.info(f"Recovering S3 access for bucket: {S3_BUCKET}")

    try:
        # Remove any deny policies (restore access)
        try:
            current_policy = json.loads(
                s3.get_bucket_policy(Bucket=S3_BUCKET)["Policy"]
            )

            # Filter out deny statements injected by DisasterZero
            clean_statements = [
                stmt for stmt in current_policy.get("Statement", [])
                if not stmt.get("Sid", "").startswith("DisasterZeroDeny")
            ]

            if clean_statements:
                clean_policy = {
                    "Version": "2012-10-17",
                    "Statement": clean_statements,
                }
                s3.put_bucket_policy(
                    Bucket=S3_BUCKET,
                    Policy=json.dumps(clean_policy),
                )
            else:
                s3.delete_bucket_policy(Bucket=S3_BUCKET)

        except s3.exceptions.from_code("NoSuchBucketPolicy"):
            pass  # No policy to clean

        return {
            "action": "s3_policy_restore",
            "bucket": S3_BUCKET,
            "status": "success",
        }

    except Exception as e:
        logger.error(f"S3 recovery failed: {e}")
        return {"action": "s3_policy_restore", "status": "failed", "error": str(e)}


def handle_lambda_alarm(alarm_name: str, alarm_data: dict) -> dict:
    """Handle Lambda function alarms (log only — Lambda is self-healing)."""
    return {
        "action": "lambda_alarm_acknowledged",
        "alarm": alarm_name,
        "status": "acknowledged",
        "note": "Lambda functions are self-healing; alarm logged for audit.",
    }


def log_incident(alarm_name: str, result: dict):
    """Write incident record to DynamoDB."""
    if not INCIDENTS_TABLE:
        logger.warning("No incidents table configured — skipping log")
        return

    try:
        table = dynamodb.Table(INCIDENTS_TABLE)
        now = datetime.now(timezone.utc).isoformat()

        table.put_item(Item={
            "incident_id": f"AUTO-{now.replace(':', '-')}",
            "created_at": now,
            "alarm_name": alarm_name,
            "failure_type": result.get("action", "unknown"),
            "status": result.get("status", "unknown"),
            "environment": ENVIRONMENT,
            "details": json.dumps(result),
            "source": "lambda_auto_recovery",
        })

        logger.info(f"Incident logged to {INCIDENTS_TABLE}")

    except Exception as e:
        logger.error(f"Failed to log incident: {e}")

