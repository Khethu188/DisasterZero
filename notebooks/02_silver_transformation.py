# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Transformation
# MAGIC
# MAGIC **Layer:** Silver (Cleaned & Validated)
# MAGIC **Source:** `transactions.bronze.raw_transactions`
# MAGIC **Target:** `transactions.silver.processed`
# MAGIC
# MAGIC Applies cleansing, type casting, deduplication, and validation.
# MAGIC This is the primary target for DisasterZero's data corruption
# MAGIC scenarios and quality gate validation.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

BRONZE_TABLE = "transactions.bronze.raw_transactions"
SILVER_TABLE = "transactions.silver.processed"
QUARANTINE_TABLE = "transactions.quarantine.rejected"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read Bronze

# COMMAND ----------

bronze_df = spark.table(BRONZE_TABLE)
print(f"Bronze records: {bronze_df.count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Deduplication
# MAGIC
# MAGIC Window function to keep only the latest record per transaction_id.

# COMMAND ----------

window = Window.partitionBy("transaction_id").orderBy(F.col("_ingested_at").desc())

deduped = (
    bronze_df
    .withColumn("_row_num", F.row_number().over(window))
    .filter(F.col("_row_num") == 1)
    .drop("_row_num")
)

print(f"After dedup: {deduped.count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validation Rules
# MAGIC
# MAGIC These mirror DisasterZero Quality Gate rules SLV-001 through SLV-010:
# MAGIC - `transaction_id` NOT NULL (SLV-001)
# MAGIC - `amount` NOT NULL and >= 0 (SLV-002, SLV-005)
# MAGIC - `currency` is valid 3-letter code (SLV-006)
# MAGIC - `status` NOT NULL (SLV-004)
# MAGIC - `timestamp` not in the future (SLV-007)

# COMMAND ----------

valid_currencies = [
    "USD", "EUR", "GBP", "ZAR", "JPY",
    "AUD", "CAD", "CHF", "CNY", "INR",
]

valid_records = (
    deduped
    .filter(F.col("transaction_id").isNotNull())
    .filter(F.col("amount").isNotNull())
    .filter(F.col("amount") >= 0)
    .filter(F.col("currency").isin(valid_currencies))
    .filter(F.col("status").isNotNull())
    .filter(F.col("timestamp") <= F.current_timestamp())
)

invalid_records = (
    deduped
    .filter(
        F.col("transaction_id").isNull()
        | F.col("amount").isNull()
        | (F.col("amount") < 0)
        | ~F.col("currency").isin(valid_currencies)
        | F.col("status").isNull()
        | (F.col("timestamp") > F.current_timestamp())
    )
)

print(f"Valid: {valid_records.count()}, Invalid: {invalid_records.count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quarantine Invalid Records

# COMMAND ----------

(
    invalid_records
    .withColumn("_quarantine_reason", F.lit("Silver validation failure"))
    .withColumn("_quarantined_at", F.current_timestamp())
    .write
    .format("delta")
    .mode("append")
    .saveAsTable(QUARANTINE_TABLE)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Enrich and Write Silver

# COMMAND ----------

silver_df = (
    valid_records
    .withColumn("amount", F.col("amount").cast("decimal(18,2)"))
    .withColumn("currency", F.upper(F.trim(F.col("currency"))))
    .withColumn("status", F.upper(F.trim(F.col("status"))))
    .withColumn("processed_at", F.current_timestamp())
    .withColumn("_silver_version", F.lit(1))
    .select(
        "transaction_id", "customer_id", "amount", "currency",
        "status", "merchant", "category", "timestamp",
        "processed_at", "_source_file", "_silver_version",
    )
)

(
    silver_df.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(SILVER_TABLE)
)

print(f"Silver table written: {spark.table(SILVER_TABLE).count()} records")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Post-Write Quality Check

# COMMAND ----------

silver = spark.table(SILVER_TABLE)

checks = {
    "SLV-001 null_transaction_id": silver.filter(F.col("transaction_id").isNull()).count(),
    "SLV-002 null_amount": silver.filter(F.col("amount").isNull()).count(),
    "SLV-005 negative_amount": silver.filter(F.col("amount") < 0).count(),
    "SLV-006 invalid_currency": silver.filter(~F.col("currency").isin(valid_currencies)).count(),
    "SLV-010 duplicates": silver.count() - silver.select("transaction_id").distinct().count(),
}

print("Silver Quality Checks:")
for check, violations in checks.items():
    status = "PASS" if violations == 0 else f"FAIL ({violations} violations)"
    print(f"  {check}: {status}")
