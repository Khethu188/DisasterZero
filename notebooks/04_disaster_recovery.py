# Databricks notebook source
# MAGIC %md
# MAGIC # Disaster Recovery
# MAGIC
# MAGIC Demonstrates Delta Lake time-travel for disaster recovery.
# MAGIC When DisasterZero detects data corruption in the Silver layer,
# MAGIC it uses these operations to rollback to the last known good state.
# MAGIC
# MAGIC **This is the core of what makes DisasterZero possible on Databricks.**

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Check Table History
# MAGIC
# MAGIC Delta Lake maintains a full transaction log. Every write, update,
# MAGIC and delete is versioned. This enables point-in-time recovery.

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE HISTORY transactions.silver.processed

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Inspect Current State

# COMMAND ----------

from pyspark.sql import functions as F

silver = spark.table("transactions.silver.processed")
print(f"Current record count: {silver.count()}")
print(f"Null transaction_ids: {silver.filter(F.col('transaction_id').isNull()).count()}")
print(f"Negative amounts: {silver.filter(F.col('amount') < 0).count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Simulate Corruption
# MAGIC
# MAGIC DisasterZero's simulator injects corrupt records like this.
# MAGIC In production, this runs via the `DatabricksFailureSimulator` class.

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType, DecimalType, TimestampType
from datetime import datetime
from decimal import Decimal

corrupt_schema = StructType([
    StructField("transaction_id", StringType()),
    StructField("customer_id", StringType()),
    StructField("amount", DecimalType(18, 2)),
    StructField("currency", StringType()),
    StructField("status", StringType()),
    StructField("merchant", StringType()),
    StructField("category", StringType()),
    StructField("timestamp", TimestampType()),
    StructField("processed_at", TimestampType()),
    StructField("_source_file", StringType()),
    StructField("_silver_version", StringType()),
])

corrupt_data = [
    # NULL transaction_id (violates SLV-001)
    (None, "CUST-999", Decimal("100.00"), "USD", "COMPLETED",
     "BadMerchant", "test", datetime.now(), datetime.now(), "corrupt", "1"),
    # Negative amount (violates SLV-005)
    ("TXN-CORRUPT-1", "CUST-999", Decimal("-500.00"), "USD", "COMPLETED",
     "BadMerchant", "test", datetime.now(), datetime.now(), "corrupt", "1"),
    # Invalid currency + NULL status (violates SLV-004, SLV-006)
    ("TXN-CORRUPT-2", "CUST-999", Decimal("200.00"), "INVALID", None,
     "BadMerchant", "test", datetime.now(), datetime.now(), "corrupt", "1"),
]

corrupt_df = spark.createDataFrame(corrupt_data, corrupt_schema)
corrupt_df.write.format("delta").mode("append").saveAsTable(
    "transactions.silver.processed"
)

print("Corrupt records injected.")
corrupted = spark.table("transactions.silver.processed")
print(f"Records after corruption: {corrupted.count()}")
print(f"Null IDs: {corrupted.filter(F.col('transaction_id').isNull()).count()}")
print(f"Negative amounts: {corrupted.filter(F.col('amount') < 0).count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Time-Travel Recovery
# MAGIC
# MAGIC Delta Lake RESTORE rolls back the table to a previous version.
# MAGIC DisasterZero's Recovery Engine calls this via the Databricks SQL API.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Check versions available
# MAGIC DESCRIBE HISTORY transactions.silver.processed

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Restore to version before corruption
# MAGIC RESTORE TABLE transactions.silver.processed TO VERSION AS OF 1

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Verify Recovery
# MAGIC
# MAGIC After rollback, DisasterZero's quality gate runs all 10 Silver
# MAGIC rules to confirm data integrity has been restored.

# COMMAND ----------

recovered = spark.table("transactions.silver.processed")
print(f"Records after recovery: {recovered.count()}")

checks = {
    "SLV-001 null_transaction_id": recovered.filter(
        F.col("transaction_id").isNull()
    ).count(),
    "SLV-002 null_amount": recovered.filter(
        F.col("amount").isNull()
    ).count(),
    "SLV-005 negative_amount": recovered.filter(
        F.col("amount") < 0
    ).count(),
    "SLV-010 duplicates": (
        recovered.count()
        - recovered.select("transaction_id").distinct().count()
    ),
}

print("\nPost-Recovery Quality Check:")
for rule, violations in checks.items():
    print(f"  {rule}: {'PASS' if violations == 0 else f'FAIL ({violations})'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC The disaster recovery flow:
# MAGIC
# MAGIC 1. **Normal state** -- Clean Silver table with validated data
# MAGIC 2. **Corruption** -- Bad records injected (NULLs, negatives, invalid codes)
# MAGIC 3. **Detection** -- Quality gate catches violations
# MAGIC 4. **Recovery** -- Delta Lake RESTORE rolls back to clean version
# MAGIC 5. **Verification** -- Quality rules confirm data integrity restored
# MAGIC
# MAGIC In production, DisasterZero automates this entire flow via
# MAGIC `DatabricksFailureSimulator`, `FailureDetector`, `RecoveryEngine`,
# MAGIC and `DataTrustQualityGate`.
