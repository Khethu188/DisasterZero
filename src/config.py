
"""
src/config.py
─────────────
Central configuration for DisasterZero.
All components import their settings from here.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════

class Environment(Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class FailureType(Enum):
    DATABRICKS_JOB_FAILURE = "databricks_job_failure"
    DATABRICKS_CLUSTER_TERMINATION = "databricks_cluster_termination"
    PIPELINE_CORRUPTION = "pipeline_corruption"
    EC2_INSTANCE_STOP = "ec2_instance_stop"
    S3_ACCESS_DENIED = "s3_access_denied"


# ═══════════════════════════════════════════════════════════════
# Sub-Configs
# ═══════════════════════════════════════════════════════════════

@dataclass
class DatabricksConfig:
    host: str = ""
    token: str = ""
    warehouse_id: str = ""
    job_id: str = ""
    cluster_id: str = ""
    catalog: str = "transactions"
    bronze_schema: str = "bronze"
    silver_schema: str = "silver"
    gold_schema: str = "gold"
    quarantine_schema: str = "quarantine"

    @property
    def bronze_table(self) -> str:
        return f"{self.catalog}.{self.bronze_schema}.raw_transactions"

    @property
    def silver_table(self) -> str:
        return f"{self.catalog}.{self.silver_schema}.processed"

    @property
    def gold_daily_summary(self) -> str:
        return f"{self.catalog}.{self.gold_schema}.daily_summary"

    @property
    def gold_risk_scores(self) -> str:
        return f"{self.catalog}.{self.gold_schema}.risk_scores"

    @property
    def quarantine_table(self) -> str:
        return f"{self.catalog}.{self.quarantine_schema}.flagged_records"

    @property
    def quality_audit_table(self) -> str:
        return f"{self.catalog}.{self.gold_schema}.quality_audit_log"


@dataclass
class AWSConfig:
    region: str = "af-south-1"
    account_id: str = ""


@dataclass
class S3Config:
    bucket_name: str = ""
    raw_prefix: str = "raw/transactions/"
    processed_prefix: str = "processed/"
    quarantine_prefix: str = "quarantine/"
    reports_prefix: str = "reports/"
    backups_prefix: str = "backups/"


@dataclass
class EC2Config:
    instance_id: str = ""


@dataclass
class RTOTarget:
    """Recovery Time Objective — max time from failure to recovery."""
    target_seconds: float = 600.0  # 10 minutes default


@dataclass
class RPOTarget:
    """Recovery Point Objective — max acceptable data loss."""
    target_records: int = 0       # Zero data loss default
    target_seconds: float = 60.0  # Max 60s of data loss


# ═══════════════════════════════════════════════════════════════
# Main Config
# ═══════════════════════════════════════════════════════════════

@dataclass
class DisasterZeroConfig:
    """Central configuration object for DisasterZero."""

    environment: Environment = Environment.DEV
    databricks: DatabricksConfig = field(default_factory=DatabricksConfig)
    aws: AWSConfig = field(default_factory=AWSConfig)
    s3: S3Config = field(default_factory=S3Config)
    ec2: EC2Config = field(default_factory=EC2Config)
    rto: RTOTarget = field(default_factory=RTOTarget)
    rpo: RPOTarget = field(default_factory=RPOTarget)

    @classmethod
    def from_env(cls) -> "DisasterZeroConfig":
        """Load configuration from environment variables."""
        env_str = os.getenv("ENVIRONMENT", "dev").lower()
        try:
            environment = Environment(env_str)
        except ValueError:
            environment = Environment.DEV

        return cls(
            environment=environment,
            databricks=DatabricksConfig(
                host=os.getenv("DATABRICKS_HOST", ""),
                token=os.getenv("DATABRICKS_TOKEN", ""),
                warehouse_id=os.getenv("DATABRICKS_WAREHOUSE_ID", ""),
                job_id=os.getenv("DATABRICKS_JOB_ID", ""),
                cluster_id=os.getenv("DATABRICKS_CLUSTER_ID", ""),
            ),
            aws=AWSConfig(
                region=os.getenv("AWS_REGION", "af-south-1"),
                account_id=os.getenv("AWS_ACCOUNT_ID", ""),
            ),
            s3=S3Config(
                bucket_name=os.getenv("S3_BUCKET", ""),
            ),
            ec2=EC2Config(
                instance_id=os.getenv("EC2_INSTANCE_ID", ""),
            ),
            rto=RTOTarget(
                target_seconds=float(os.getenv("RTO_TARGET_SECONDS", "600")),
            ),
            rpo=RPOTarget(
                target_records=int(os.getenv("RPO_TARGET_RECORDS", "0")),
                target_seconds=float(os.getenv("RPO_TARGET_SECONDS", "60")),
            ),
        )

