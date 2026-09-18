# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Ingestion
# MAGIC
# MAGIC **Layer:** Bronze (Raw)
# MAGIC **Source:** Landing zone (S3 / ADLS)
# MAGIC **Target:** `transactions.bronze.raw_transactions`
# MAGIC
# MAGIC Ingests raw transaction data using Auto Loader with schema evolution.
# MAGIC This notebook runs as part of the DisasterZero Medallion pipeline
# MAGIC and is a primary failure injection target.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType

CATALOG = "transactions"
BRONZE_SCHEMA = "bronze"
BRONZE_TABLE = f"{CATALOG}.{BRONZE_SCHEMA}.raw_transactions"
CHECKPOINT = "/Volumes/transactions/checkpoints/bronze_ingest"
LANDING_ZONE = "/Volumes/transactions/landing/raw/"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Schema Definition

# COMMAND ----------

raw_schema = StructType([
    StructField("transaction_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("currency", StringType(), True),
    StructField("status", StringType(), True),
    StructField("merchant", StringType(), True),
    StructField("category", StringType(), True),
    StructField("timestamp", TimestampType(), True),
])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Auto Loader Ingestion
# MAGIC
# MAGIC Uses Structured Streaming with `cloudFiles` for:
# MAGIC - Automatic schema detection and evolution
# MAGIC - Exactly-once processing guarantees
# MAGIC - Incremental file discovery

# COMMAND ----------

bronze_df = (
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", f"{CHECKPOINT}/schema")
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
    .option("cloudFiles.inferColumnTypes", "true")
    .schema(raw_schema)
    .load(LANDING_ZONE)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Add Metadata Columns

# COMMAND ----------

bronze_enriched = (
    bronze_df
    .withColumn("_ingested_at", F.current_timestamp())
    .withColumn("_source_file", F.input_file_name())
    .withColumn("_ingestion_date", F.current_date())
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Bronze Table
# MAGIC
# MAGIC Delta Lake with append mode. Partitioned by ingestion date for
# MAGIC efficient time-travel queries during disaster recovery rollbacks.

# COMMAND ----------

(
    bronze_enriched.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", CHECKPOINT)
    .option("mergeSchema", "true")
    .partitionBy("_ingestion_date")
    .trigger(availableNow=True)
    .toTable(BRONZE_TABLE)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validation

# COMMAND ----------

record_count = spark.table(BRONZE_TABLE).count()
print(f"Bronze table record count: {record_count}")

latest = spark.sql(f"""
    SELECT MAX(_ingested_at) as latest_ingestion,
           COUNT(*) as total_records,
           COUNT(DISTINCT _ingestion_date) as partition_count
    FROM {BRONZE_TABLE}
""")
latest.display()
