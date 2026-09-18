
"""
databricks/notebooks/transaction_ingestion.py
─────────────────────────────────────────────
Ingests raw transaction data from S3 into Bronze layer.
Run this in a Databricks notebook or as a Lakeflow Job task.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, input_file_name
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, TimestampType
)

spark = SparkSession.builder.getOrCreate()

# ── Configuration ──
S3_RAW_PATH = "s3://disasterzero-data/raw/transactions/"
BRONZE_TABLE = "transactions.bronze.raw_transactions"

# ── Schema ──
transaction_schema = StructType([
    StructField("transaction_id", StringType(), False),
    StructField("account_id", StringType(), False),
    StructField("amount", DoubleType(), True),
    StructField("currency", StringType(), True),
    StructField("merchant", StringType(), True),
    StructField("category", StringType(), True),
    StructField("timestamp", TimestampType(), True),
    StructField("status", StringType(), True),
])

# ── Ingest ──
df_raw = (
    spark.read
    .schema(transaction_schema)
    .json(S3_RAW_PATH)
    .withColumn("ingested_at", current_timestamp())
    .withColumn("source_file", input_file_name())
)

# Write to Bronze (append mode for incremental)
(
    df_raw.write
    .format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(BRONZE_TABLE)
)

print(f"Ingested {df_raw.count()} records into {BRONZE_TABLE}")


# ─────────────────────────────────────────────────────────────
# databricks/notebooks/transaction_transformation.py
# ─────────────────────────────────────────────────────────────
"""
Transforms Bronze → Silver with cleaning, validation, deduplication.
This is the task that DisasterZero will target for failure simulation.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, current_timestamp, when, lit, row_number, abs as spark_abs
)
from pyspark.sql.window import Window

spark = SparkSession.builder.getOrCreate()

BRONZE_TABLE = "transactions.bronze.raw_transactions"
SILVER_TABLE = "transactions.silver.processed"
