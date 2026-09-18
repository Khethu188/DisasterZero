
"""
tests/unit/test_simulator.py
────────────────────────────
Tests for the failure simulator (chaos injection).
"""

import pytest
from unittest.mock import MagicMock, patch

from src.config import FailureType


class TestDatabricksFailureSimulator:
    """Test Databricks failure injection."""

    def test_inject_job_failure(self, config, mock_databricks_api):
        from src.simulator.databricks_failures import DatabricksFailureSimulator

        simulator = DatabricksFailureSimulator(config)
        result = simulator.inject_failure(FailureType.DATABRICKS_JOB_FAILURE)

        assert result is not None
        assert result.failure_type == FailureType.DATABRICKS_JOB_FAILURE

    def test_inject_data_corruption(self, config, mock_databricks_api):
        from src.simulator.databricks_failures import DatabricksFailureSimulator

        simulator = DatabricksFailureSimulator(config)
        result = simulator.inject_failure(
            FailureType.PIPELINE_CORRUPTION,
            table_name="transactions.silver.processed",
        )

        assert result is not None

    def test_cleanup_after_injection(self, config, mock_databricks_api):
        """Simulator should provide cleanup capability."""
        from src.simulator.databricks_failures import DatabricksFailureSimulator

        simulator = DatabricksFailureSimulator(config)
        result = simulator.inject_failure(FailureType.DATABRICKS_JOB_FAILURE)

        # Cleanup should not raise
        simulator.cleanup(result)


class TestAWSFailureSimulator:
    """Test AWS failure injection (EC2, S3)."""

    def test_inject_ec2_stop(self, config, mock_aws_clients):
        from src.simulator.aws_failures import AWSFailureSimulator

        simulator = AWSFailureSimulator(config)
        result = simulator.inject_failure(FailureType.EC2_INSTANCE_STOP)

        mock_aws_clients["ec2"].stop_instances.assert_called_once()

    def test_inject_s3_access_denied(self, config, mock_aws_clients):
        from src.simulator.aws_failures import AWSFailureSimulator

        simulator = AWSFailureSimulator(config)
        result = simulator.inject_failure(FailureType.S3_ACCESS_DENIED)

        mock_aws_clients["s3"].put_bucket_policy.assert_called_once()

    def test_cleanup_ec2(self, config, mock_aws_clients):
        from src.simulator.aws_failures import AWSFailureSimulator

        simulator = AWSFailureSimulator(config)
        result = simulator.inject_failure(FailureType.EC2_INSTANCE_STOP)
        simulator.cleanup(result)

        mock_aws_clients["ec2"].start_instances.assert_called()

    def test_cleanup_s3(self, config, mock_aws_clients):
        from src.simulator.aws_failures import AWSFailureSimulator

        simulator = AWSFailureSimulator(config)
        result = simulator.inject_failure(FailureType.S3_ACCESS_DENIED)
        simulator.cleanup(result)

        # Should restore or delete the deny policy
        s3 = mock_aws_clients["s3"]
        assert (
            s3.put_bucket_policy.called or s3.delete_bucket_policy.called
        )

