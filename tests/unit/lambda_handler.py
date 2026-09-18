
"""
tests/unit/test_lambda_handler.py
─────────────────────────────────
Tests for the Lambda auto-recovery handler.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

# Mock environment variables before import
import os
os.environ["ENVIRONMENT"] = "dev"
os.environ["PROJECT"] = "disasterzero"
os.environ["S3_BUCKET"] = "disasterzero-test-bucket"
os.environ["INCIDENTS_TABLE"] = "disasterzero-dev-incidents"
os.environ["APP_INSTANCE_ID"] = "i-0test123instance"


class TestLambdaHandler:
    """Test the Lambda recovery handler."""

    def _make_sns_event(self, alarm_name: str, state: str = "ALARM") -> dict:
        """Create a mock SNS → CloudWatch alarm event."""
        return {
            "Records": [{
                "Sns": {
                    "Message": json.dumps({
                        "AlarmName": alarm_name,
                        "NewStateValue": state,
                        "NewStateReason": "Threshold crossed",
                        "StateChangeTime": "2026-09-18T08:00:00.000+0000",
                    })
                }
            }]
        }

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_ec2_alarm_triggers_restart(self, mock_resource, mock_client):
        """EC2 status alarm should trigger instance restart."""
        from terraform.modules.compute.lambda_pkg.handler import lambda_handler

        ec2 = MagicMock()
        mock_client.return_value = ec2
        ec2.describe_instances.return_value = {
            "Reservations": [{
                "Instances": [{
                    "InstanceId": "i-0test123instance",
                    "State": {"Name": "stopped"},
                }]
            }]
        }

        # Mock DynamoDB table
        table = MagicMock()
        mock_resource.return_value.Table.return_value = table

        event = self._make_sns_event("disasterzero-dev-ec2-status-check")
        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        ec2.start_instances.assert_called_once()

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_ec2_already_running_no_action(self, mock_resource, mock_client):
        """If EC2 is already running, no restart needed."""
        from terraform.modules.compute.lambda_pkg.handler import lambda_handler

        ec2 = MagicMock()
        mock_client.return_value = ec2
        ec2.describe_instances.return_value = {
            "Reservations": [{
                "Instances": [{
                    "InstanceId": "i-0test123instance",
                    "State": {"Name": "running"},
                }]
            }]
        }

        table = MagicMock()
        mock_resource.return_value.Table.return_value = table

        event = self._make_sns_event("disasterzero-dev-ec2-status-check")
        result = lambda_handler(event, None)

        body = json.loads(result["body"])
        assert body["status"] == "already_running"
        ec2.start_instances.assert_not_called()

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_s3_alarm_restores_policy(self, mock_resource, mock_client):
        """S3 access alarm should restore bucket policy."""
        from terraform.modules.compute.lambda_pkg.handler import lambda_handler

        s3 = MagicMock()
        mock_client.return_value = s3
        s3.get_bucket_policy.return_value = {
            "Policy": json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {"Sid": "DisasterZeroDenyAll", "Effect": "Deny", "Action": "*", "Resource": "*"},
                    {"Sid": "LegitPolicy", "Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"},
                ],
            })
        }

        table = MagicMock()
        mock_resource.return_value.Table.return_value = table

        event = self._make_sns_event("disasterzero-dev-s3-access-errors")
        result = lambda_handler(event, None)

        assert result["statusCode"] == 200

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_non_alarm_state_ignored(self, mock_resource, mock_client):
        """OK state should be ignored (no recovery action)."""
        from terraform.modules.compute.lambda_pkg.handler import lambda_handler

        table = MagicMock()
        mock_resource.return_value.Table.return_value = table

        event = self._make_sns_event("disasterzero-dev-ec2-status-check", state="OK")
        result = lambda_handler(event, None)

        # Should return without taking action
        assert result is None or result.get("statusCode") == 200

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_incident_logged_to_dynamodb(self, mock_resource, mock_client):
        """Every recovery action should be logged to DynamoDB."""
        from terraform.modules.compute.lambda_pkg.handler import lambda_handler

        ec2 = MagicMock()
        mock_client.return_value = ec2
        ec2.describe_instances.return_value = {
            "Reservations": [{
                "Instances": [{
                    "InstanceId": "i-0test123instance",
                    "State": {"Name": "stopped"},
                }]
            }]
        }

        table = MagicMock()
        mock_resource.return_value.Table.return_value = table

        event = self._make_sns_event("disasterzero-dev-ec2-status-check")
        lambda_handler(event, None)

        table.put_item.assert_called_once()
        item = table.put_item.call_args[1]["Item"]
        assert item["incident_id"].startswith("AUTO-")
        assert item["environment"] == "dev"

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_unknown_alarm_handled_gracefully(self, mock_resource, mock_client):
        """Unknown alarm types should be logged but not crash."""
        from terraform.modules.compute.lambda_pkg.handler import lambda_handler

        table = MagicMock()
        mock_resource.return_value.Table.return_value = table

        event = self._make_sns_event("some-random-alarm-name")
        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "skipped"

