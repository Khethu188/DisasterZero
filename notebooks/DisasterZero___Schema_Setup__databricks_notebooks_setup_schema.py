
"""
databricks/notebooks/setup_schema.py
─────────────────────────────────────
Run this ONCE to create the Unity Catalog schema and tables.
"""

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# ═══════════════════════════════════════════════════════════════
# Create Catalog & Schemas
# ═══════════════════════════════════════════════════════════════
spark.sql("CREATE CATALOG IF NOT EXISTS transactions")
spark.sql("CREATE SCHEMA IF NOT EXISTS transactions.bronze")
spark.sql("CREATE SCHEMA IF NOT EXISTS transactions.silver")
spark.sql("CREATE SCHEMA IF NOT EXISTS transactions.gold")
spark.sql("CREATE SCHEMA IF NOT EXISTS transactions.quarantine")

print("✓ Catalog and schemas created")

# ═══════════════════════════════════════════════════════════════
# Bronze Table
# ═══════════════════════════════════════════════════════════════
spark.sql("""
    CREATE TABLE IF NOT EXISTS transactions.bronze.raw_transactions (
        transaction_id STRING NOT NULL,
        account_id STRING,
        amount DOUBLE,
        currency STRING,
        merchant STRING,
        category STRING,
        timestamp TIMESTAMP,
        status STRING,
        ingested_at TIMESTAMP,
        source_file STRING
    )
    USING DELTA
    COMMENT 'Raw transaction data ingested from S3'
    TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true',
        'delta.logRetentionDuration' = 'interval 30 days',
        'delta.deletedFileRetentionDuration' = 'interval 30 days'
    )
""")

# ═══════════════════════════════════════════════════════════════
# Silver Table
# ═══════════════════════════════════════════════════════════════
spark.sql("""
    CREATE TABLE IF NOT EXISTS transactions.silver.processed (
        transaction_id STRING NOT NULL,
        account_id STRING NOT NULL,
        amount DOUBLE NOT NULL,
        currency STRING NOT NULL,
        merchant STRING,
        category STRING,
        timestamp TIMESTAMP NOT NULL,
        status STRING,
        amount_abs DOUBLE,
        size_category STRING,
        requires_review BOOLEAN,
        processed_at TIMESTAMP,
        ingested_at TIMESTAMP
    )
    USING DELTA
    COMMENT 'Cleaned, validated, deduplicated transactions'
    TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true',
        'delta.logRetentionDuration' = 'interval 30 days',
        'delta.deletedFileRetentionDuration' = 'interval 30 days'
    )
""")

# ═══════════════════════════════════════════════════════════════
# Quarantine Table
# ═══════════════════════════════════════════════════════════════
spark.sql("""
    CREATE TABLE IF NOT EXISTS transactions.quarantine.records (
        transaction_id STRING,
        account_id STRING,
        amount DOUBLE,
        currency STRING,
        merchant STRING,
        category STRING,
        timestamp TIMESTAMP,
        status STRING,
        ingested_at TIMESTAMP,
        source_file STRING,
        quality_status STRING,
        quarantined_at TIMESTAMP,
        reason STRING,
        source_layer STRING
    )
    USING DELTA
    COMMENT 'Records that failed data quality validation'
""")

# ═══════════════════════════════════════════════════════════════
# Gold Tables
# ═══════════════════════════════════════════════════════════════
spark.sql("""
    CREATE TABLE IF NOT EXISTS transactions.gold.daily_summary (
        transaction_date STRING,
        currency STRING,
        total_transactions LONG,
        total_amount DOUBLE,
        avg_amount DOUBLE,
        min_amount DOUBLE,
        max_amount DOUBLE,
        unique_accounts LONG,
        xlarge_count LONG,
        review_required_count LONG,
        reversed_count LONG,
        declined_count LONG,
        generated_at TIMESTAMP
    )
    USING DELTA
    COMMENT 'Daily aggregated transaction metrics'
""")

spark.sql("""
    CREATE TABLE IF NOT EXISTS transactions.gold.account_metrics (
        account_id STRING,
        total_transactions LONG,
        total_spent DOUBLE,
        avg_transaction DOUBLE,
        max_transaction DOUBLE,
        unique_merchants LONG,
        unique_categories LONG,
        active_days LONG,
        reversal_count LONG,
        decline_count LONG,
        first_transaction TIMESTAMP,
        last_transaction TIMESTAMP,
        reversal_rate DOUBLE,
        decline_rate DOUBLE,
        generated_at TIMESTAMP
    )
    USING DELTA
    COMMENT 'Account-level transaction metrics'
""")

spark.sql("""
    CREATE TABLE IF NOT EXISTS transactions.gold.risk_scores (
        account_id STRING,
        total_transactions LONG,
        total_spent DOUBLE,
        reversal_rate DOUBLE,
        decline_rate DOUBLE,
        max_transaction DOUBLE,
        unique_merchants LONG,
        risk_score INT,
        risk_level STRING,
        generated_at TIMESTAMP
    )
    USING DELTA
    COMMENT 'Account risk scoring for fraud detection'
""")

spark.sql("""
    CREATE TABLE IF NOT EXISTS transactions.gold.pipeline_health (
        snapshot_timestamp STRING,
        bronze_record_count LONG,
        silver_record_count LONG,
        quarantine_record_count LONG,
        daily_summary_rows LONG,
        accounts_scored LONG,
        high_risk_accounts LONG,
        data_loss_rate DOUBLE,
        pipeline_status STRING
    )
    USING DELTA
    COMMENT 'Pipeline health snapshots — used by DisasterZero for verification'
""")

print("✓ All tables created")
print("""
Run order:
  1. generate_sample_data       → populate S3/DBFS with raw data
  2. transaction_ingestion      → Bronze layer
  3. transaction_transformation → Silver layer
  4. transaction_analytics      → Gold layer
""")

