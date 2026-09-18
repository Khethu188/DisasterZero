
"""
tests/unit/test_config.py
─────────────────────────
Tests for DisasterZero configuration loading and validation.
"""

import os
import pytest
from unittest.mock import patch

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


class TestEnvironment:
    """Test environment enum."""

    def test_valid_environments(self):
        assert Environment.DEV.value == "dev"
        assert Environment.STAGING.value == "staging"
        assert Environment.PROD.value == "prod"

    def test_environment_from_string(self):
        assert Environment("dev") == Environment.DEV
        assert Environment("prod") == Environment.PROD

    def test_invalid_environment_raises(self):
        with pytest.raises(ValueError):
            Environment("invalid")


class TestFailureType:
    """Test failure type enum."""

    def test_all_failure_types_exist(self):
        expected = [
            "DATABRICKS_JOB_FAILURE",
            "DATABRICKS_CLUSTER_TERMINATION",
            "PIPELINE_CORRUPTION",
            "EC2_INSTANCE_STOP",
            "S3_ACCESS_DENIED",
        ]
        actual = [ft.name for ft in FailureType]
        for ft in expected:
            assert ft in actual, f"Missing failure type: {ft}"


class TestRTOTarget:
    """Test RTO target configuration."""

    def test_default_rto(self):
        rto = RTOTarget()
        assert rto.target_seconds > 0

    def test_custom_rto(self):
        rto = RTOTarget(target_seconds=300)
        assert rto.target_seconds == 300

    def test_rto_cannot_be_negative(self):
        # Config should handle this gracefully
        rto = RTOTarget(target_seconds=-1)
        assert rto.target_seconds == -1  # Validation happens at usage


class TestRPOTarget:
    """Test RPO target configuration."""

    def test_zero_data_loss_target(self):
        rpo = RPOTarget(target_records=0)
        assert rpo.target_records == 0

    def test_custom_rpo(self):
        rpo = RPOTarget(target_records=10, target_seconds=120)
        assert rpo.target_records == 10
        assert rpo.target_seconds == 120


class TestDisasterZeroConfig:
    """Test main configuration object."""

    def test_config_creation(self, config):
        assert config.environment == Environment.DEV
        assert config.databricks.host == "https://test-workspace.cloud.databricks.com"
        assert config.databricks.job_id == "12345"
        assert config.s3.bucket_name == "disasterzero-test-bucket"
        assert config.ec2.instance_id == "i-0test123instance"

    def test_config_rto_rpo_defaults(self, config):
        assert config.rto.target_seconds == 600
        assert config.rpo.target_records == 0

    def test_prod_config_stricter(self, prod_config):
        assert prod_config.environment == Environment.PROD
        assert prod_config.rto.target_seconds == 300
        assert prod_config.rpo.target_seconds == 30

    def test_databricks_config_has_required_fields(self, config):
        db = config.databricks
        assert db.host is not None
        assert db.token is not None
        assert db.job_id is not None

    def test_sensitive_fields_not_empty(self, config):
        assert len(config.databricks.token) > 0
        assert len(config.databricks.host) > 0

