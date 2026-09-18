
"""
databricks/notebooks/transaction_transformation.py
───────────────────────────────────────────────────
Transforms Bronze → Silver with cleaning, validation, deduplication.
This is the task that DisasterZero will target for failure simulation.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, current_timestamp, when, lit, row_number,
    abs as spark_abs, upper, trim, count, sum as spark_sum
)
from pyspark.sql.window import Window

spark = SparkSession.builder.getOrCreate()

# ── Configuration ──
BRONZE_TABLE = "transactions.bronze.raw_transactions"
SILVER_TABLE = "transactions.silver.processed"
QUARANTINE_TABLE = "transactions.quarantine.records"
VALID_CURRENCIES = ["USD", "EUR", "GBP", "ZAR", "JPY", "CAD", "AUD"]
VALID_STATUSES = ["COMPLETED", "PENDING", "REVERSED", "DECLINED"]


# ═══════════════════════════════════════════════════════════════
# STEP 1: Read Bronze
# ═══════════════════════════════════════════════════════════════
df_bronze = spark.read.table(BRONZE_TABLE)

print(f"Bronze records read: {df_bronze.count()}")


# ═══════════════════════════════════════════════════════════════
# STEP 2: Deduplicate
# ═══════════════════════════════════════════════════════════════
# Keep the latest record per transaction_id based on ingestion time
dedup_window = Window.partitionBy("transaction_id").orderBy(col("ingested_at").desc())

df_deduped = (
    df_bronze
    .withColumn("row_num", row_number().over(dedup_window))
    .filter(col("row_num") == 1)
    .drop("row_num")
)

duplicates_removed = df_bronze.count() - df_deduped.count()
print(f"Duplicates removed: {duplicates_removed}")


# ═══════════════════════════════════════════════════════════════
# STEP 3: Data Quality Validation
# ═══════════════════════════════════════════════════════════════
df_validated = df_deduped.withColumn(
    "quality_status",
    when(col("transaction_id").isNull(), lit("FAILED_NULL_ID"))
    .when(col("amount").isNull(), lit("FAILED_NULL_AMOUNT"))
    .when(col("amount") < 0, lit("FAILED_NEGATIVE_AMOUNT"))
    .when(col("amount") > 1_000_000, lit("FAILED_AMOUNT_THRESHOLD"))
    .when(~upper(trim(col("currency"))).isin(VALID_CURRENCIES), lit("FAILED_INVALID_CURRENCY"))
    .when(col("account_id").isNull(), lit("FAILED_NULL_ACCOUNT"))
    .when(col("timestamp").isNull(), lit("FAILED_NULL_TIMESTAMP"))
    .otherwise(lit("PASSED"))
)

# Split into good and bad records
df_good = df_validated.filter(col("quality_status") == "PASSED")
df_bad = df_validated.filter(col("quality_status") != "PASSED")

print(f"Records passed validation: {df_good.count()}")
print(f"Records failed validation: {df_bad.count()}")


# ═══════════════════════════════════════════════════════════════
# STEP 4: Quarantine Bad Records
# ═══════════════════════════════════════════════════════════════
if df_bad.count() > 0:
    df_quarantine = (
        df_bad
        .withColumn("quarantined_at", current_timestamp())
        .withColumn("reason", col("quality_status"))
        .withColumn("source_layer", lit("bronze_to_silver"))
    )

    (
        df_quarantine.write
        .format("delta")
        .mode("append")
        .option("mergeSchema", "true")
        .saveAsTable(QUARANTINE_TABLE)
    )

    print(f"Quarantined {df_bad.count()} records to {QUARANTINE_TABLE}")


# ═══════════════════════════════════════════════════════════════
# STEP 5: Transform & Enrich
# ═══════════════════════════════════════════════════════════════
df_silver = (
    df_good
    .withColumn("currency", upper(trim(col("currency"))))
    .withColumn("status", upper(trim(col("status"))))
    .withColumn("amount_abs", spark_abs(col("amount")))
    .withColumn("processed_at", current_timestamp())
    # Categorize transaction size
    .withColumn(
        "size_category",
        when(col("amount") < 100, lit("SMALL"))
        .when(col("amount") < 1000, lit("MEDIUM"))
        .when(col("amount") < 10000, lit("LARGE"))
        .otherwise(lit("XLARGE"))
    )
    # Flag high-value transactions for review
    .withColumn(
        "requires_review",
        when(col("amount") > 50000, lit(True)).otherwise(lit(False))
    )
    .drop("quality_status", "source_file", "row_num")
)


# ═══════════════════════════════════════════════════════════════
# STEP 6: Write to Silver (MERGE for idempotency)
# ═══════════════════════════════════════════════════════════════
# Use MERGE to prevent duplicates on re-runs — critical for disaster recovery
df_silver.createOrReplaceTempView("silver_updates")

spark.sql(f"""
    MERGE INTO {SILVER_TABLE} AS target
    USING silver_updates AS source
    ON target.transaction_id = source.transaction_id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")

final_count = spark.read.table(SILVER_TABLE).count()
print(f"Silver table total records: {final_count}")


# ═══════════════════════════════════════════════════════════════
# STEP 7: Post-Transformation Integrity Check
# ═══════════════════════════════════════════════════════════════
# This is what DisasterZero's verifier will also check independently

integrity_checks = {
    "null_ids": spark.sql(
        f"SELECT COUNT(*) FROM {SILVER_TABLE} WHERE transaction_id IS NULL"
    ).collect()[0][0],
    "null_amounts": spark.sql(
        f"SELECT COUNT(*) FROM {SILVER_TABLE} WHERE amount IS NULL"
    ).collect()[0][0],
    "negative_amounts": spark.sql(
        f"SELECT COUNT(*) FROM {SILVER_TABLE} WHERE amount < 0"
    ).collect()[0][0],
    "duplicate_ids": spark.sql(f"""
        SELECT COUNT(*) FROM (
            SELECT transaction_id, COUNT(*) as cnt
            FROM {SILVER_TABLE}
            GROUP BY transaction_id
            HAVING cnt > 1
        )
    """).collect()[0][0],
}

all_passed = all(v == 0 for v in integrity_checks.values())
print(f"\nIntegrity Checks: {'ALL PASSED ✓' if all_passed else 'FAILURES DETECTED ✗'}")
for check, value in integrity_checks.items():
    status = "✓" if value == 0 else f"✗ ({value} issues)"
    print(f"  {check}: {status}")

if not all_passed:
    raise Exception(
        f"Post-transformation integrity check failed: {integrity_checks}"
    )

