
"""
databricks/notebooks/setup_quality_audit.py
────────────────────────────────────────────
Creates the quality gate audit table used by the DataTrust Bridge.
Run this once after setup_schema.py.
"""

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

spark.sql("""
    CREATE TABLE IF NOT EXISTS transactions.gold.quality_gate_audit (
        gate_id STRING NOT NULL,
        pipeline_run_id STRING,
        table_name STRING,
        overall_status STRING,
        total_checks INT,
        passed_checks INT,
        failed_checks INT,
        total_violations BIGINT,
        records_quarantined BIGINT,
        triggered_recovery BOOLEAN,
        evaluated_at TIMESTAMP
    )
    USING DELTA
    COMMENT 'Audit trail for DataTrust quality gate evaluations — tracks every quality check run and whether recovery was triggered'
    TBLPROPERTIES (
        'delta.logRetentionDuration' = 'interval 90 days'
    )
""")

print("✓ Quality gate audit table created: transactions.gold.quality_gate_audit")

