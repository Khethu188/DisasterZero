
"""
databricks/notebooks/transaction_analytics.py
──────────────────────────────────────────────
Builds Gold layer analytics tables from Silver.
These are the downstream tables DisasterZero verifies after recovery.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, current_timestamp, date_format, sum as spark_sum,
    count, avg, min as spark_min, max as spark_max,
    countDistinct, when, lit, round as spark_round
)

spark = SparkSession.builder.getOrCreate()

# ── Configuration ──
SILVER_TABLE = "transactions.silver.processed"
GOLD_DAILY_SUMMARY = "transactions.gold.daily_summary"
GOLD_ACCOUNT_METRICS = "transactions.gold.account_metrics"
GOLD_RISK_SCORES = "transactions.gold.risk_scores"
GOLD_PIPELINE_HEALTH = "transactions.gold.pipeline_health"


# ═══════════════════════════════════════════════════════════════
# Read Silver
# ═══════════════════════════════════════════════════════════════
df_silver = spark.read.table(SILVER_TABLE)
print(f"Silver records: {df_silver.count()}")


# ═══════════════════════════════════════════════════════════════
# GOLD TABLE 1: Daily Transaction Summary
# ═══════════════════════════════════════════════════════════════
df_daily = (
    df_silver
    .withColumn("transaction_date", date_format(col("timestamp"), "yyyy-MM-dd"))
    .groupBy("transaction_date", "currency")
    .agg(
        count("*").alias("total_transactions"),
        spark_sum("amount").alias("total_amount"),
        avg("amount").alias("avg_amount"),
        spark_min("amount").alias("min_amount"),
        spark_max("amount").alias("max_amount"),
        countDistinct("account_id").alias("unique_accounts"),
        count(when(col("size_category") == "XLARGE", True)).alias("xlarge_count"),
        count(when(col("requires_review") == True, True)).alias("review_required_count"),
        count(when(col("status") == "REVERSED", True)).alias("reversed_count"),
        count(when(col("status") == "DECLINED", True)).alias("declined_count"),
    )
    .withColumn("generated_at", current_timestamp())
    .orderBy("transaction_date", "currency")
)

(
    df_daily.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_DAILY_SUMMARY)
)

print(f"Daily summary: {df_daily.count()} rows written to {GOLD_DAILY_SUMMARY}")


# ═══════════════════════════════════════════════════════════════
# GOLD TABLE 2: Account-Level Metrics
# ═══════════════════════════════════════════════════════════════
df_accounts = (
    df_silver
    .groupBy("account_id")
    .agg(
        count("*").alias("total_transactions"),
        spark_sum("amount").alias("total_spent"),
        avg("amount").alias("avg_transaction"),
        spark_max("amount").alias("max_transaction"),
        countDistinct("merchant").alias("unique_merchants"),
        countDistinct("category").alias("unique_categories"),
        countDistinct(date_format(col("timestamp"), "yyyy-MM-dd")).alias("active_days"),
        count(when(col("status") == "REVERSED", True)).alias("reversal_count"),
        count(when(col("status") == "DECLINED", True)).alias("decline_count"),
        spark_min("timestamp").alias("first_transaction"),
        spark_max("timestamp").alias("last_transaction"),
    )
    .withColumn(
        "reversal_rate",
        spark_round(col("reversal_count") / col("total_transactions") * 100, 2)
    )
    .withColumn(
        "decline_rate",
        spark_round(col("decline_count") / col("total_transactions") * 100, 2)
    )
    .withColumn("generated_at", current_timestamp())
)

(
    df_accounts.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_ACCOUNT_METRICS)
)

print(f"Account metrics: {df_accounts.count()} rows written to {GOLD_ACCOUNT_METRICS}")


# ═══════════════════════════════════════════════════════════════
# GOLD TABLE 3: Risk Scores
# ═══════════════════════════════════════════════════════════════
# Simple rule-based risk scoring — flags accounts for review
df_risk = (
    df_accounts
    .withColumn(
        "risk_score",
        (
            # High reversal rate = risky
            when(col("reversal_rate") > 10, lit(30)).otherwise(lit(0))
            # High decline rate = risky
            + when(col("decline_rate") > 15, lit(25)).otherwise(lit(0))
            # Very high single transaction
            + when(col("max_transaction") > 50000, lit(20)).otherwise(lit(0))
            # High total spend
            + when(col("total_spent") > 500000, lit(15)).otherwise(lit(0))
            # Low merchant diversity with high spend (potential structuring)
            + when(
                (col("unique_merchants") < 3) & (col("total_spent") > 10000),
                lit(10)
            ).otherwise(lit(0))
        )
    )
    .withColumn(
        "risk_level",
        when(col("risk_score") >= 50, lit("CRITICAL"))
        .when(col("risk_score") >= 30, lit("HIGH"))
        .when(col("risk_score") >= 15, lit("MEDIUM"))
        .otherwise(lit("LOW"))
    )
    .select(
        "account_id", "total_transactions", "total_spent",
        "reversal_rate", "decline_rate", "max_transaction",
        "unique_merchants", "risk_score", "risk_level",
        "generated_at"
    )
)

(
    df_risk.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_RISK_SCORES)
)

high_risk = df_risk.filter(col("risk_level").isin("HIGH", "CRITICAL")).count()
print(f"Risk scores: {df_risk.count()} accounts scored, {high_risk} flagged HIGH/CRITICAL")


# ═══════════════════════════════════════════════════════════════
# GOLD TABLE 4: Pipeline Health Metrics
# ═══════════════════════════════════════════════════════════════
# This table tracks the health of the pipeline itself
# DisasterZero uses this to verify recovery completeness

bronze_count = spark.read.table("transactions.bronze.raw_transactions").count()
silver_count = df_silver.count()
quarantine_count = spark.sql(
    "SELECT COUNT(*) FROM transactions.quarantine.records"
).collect()[0][0]

df_health = spark.createDataFrame([{
    "snapshot_timestamp": str(current_timestamp()),
    "bronze_record_count": bronze_count,
    "silver_record_count": silver_count,
    "quarantine_record_count": quarantine_count,
    "daily_summary_rows": df_daily.count(),
    "accounts_scored": df_risk.count(),
    "high_risk_accounts": high_risk,
    "data_loss_rate": round(
        (bronze_count - silver_count - quarantine_count) / max(bronze_count, 1) * 100, 4
    ),
    "pipeline_status": "HEALTHY" if (
        bronze_count == silver_count + quarantine_count
    ) else "DATA_DISCREPANCY",
}])

(
    df_health.write
    .format("delta")
    .mode("append")
    .saveAsTable(GOLD_PIPELINE_HEALTH)
)

print(f"\n{'='*50}")
print("PIPELINE HEALTH SNAPSHOT")
print(f"{'='*50}")
print(f"  Bronze:     {bronze_count:,}")
print(f"  Silver:     {silver_count:,}")
print(f"  Quarantine: {quarantine_count:,}")
print(f"  Accounted:  {silver_count + quarantine_count:,}")
print(f"  Data Loss:  {bronze_count - silver_count - quarantine_count:,}")
print(f"  Status:     {'HEALTHY ✓' if bronze_count == silver_count + quarantine_count else 'DISCREPANCY ✗'}")
print(f"{'='*50}")

