# Databricks notebook source
# MAGIC %md
# MAGIC # Gold Aggregation
# MAGIC
# MAGIC **Layer:** Gold (Business-Ready)
# MAGIC **Source:** `transactions.silver.processed`
# MAGIC **Target:** `transactions.gold.daily_summary`
# MAGIC
# MAGIC Aggregates Silver data into business-level daily summaries.
# MAGIC Validated by DisasterZero Gold quality rules GLD-001 through GLD-004.

# COMMAND ----------

from pyspark.sql import functions as F

SILVER_TABLE = "transactions.silver.processed"
GOLD_TABLE = "transactions.gold.daily_summary"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read Silver

# COMMAND ----------

silver = spark.table(SILVER_TABLE)
print(f"Silver records: {silver.count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Daily Summary Aggregation

# COMMAND ----------

daily_summary = (
    silver
    .withColumn("summary_date", F.to_date("timestamp"))
    .groupBy("summary_date", "currency", "status")
    .agg(
        F.count("*").alias("transaction_count"),
        F.sum("amount").alias("total_amount"),
        F.avg("amount").alias("avg_amount"),
        F.min("amount").alias("min_amount"),
        F.max("amount").alias("max_amount"),
        F.countDistinct("customer_id").alias("unique_customers"),
        F.countDistinct("merchant").alias("unique_merchants"),
    )
    .withColumn("aggregated_at", F.current_timestamp())
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write Gold Table

# COMMAND ----------

(
    daily_summary.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_TABLE)
)

gold = spark.table(GOLD_TABLE)
print(f"Gold table written: {gold.count()} summary rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold Quality Checks

# COMMAND ----------

checks = {
    "GLD-001 null_summary_date": gold.filter(F.col("summary_date").isNull()).count(),
    "GLD-002 negative_total_amount": gold.filter(F.col("total_amount") < 0).count(),
    "GLD-003 zero_transaction_count": gold.filter(F.col("transaction_count") <= 0).count(),
    "GLD-004 duplicate_rows": (
        gold.count()
        - gold.select("summary_date", "currency", "status").distinct().count()
    ),
}

print("Gold Quality Checks:")
all_passed = True
for check, violations in checks.items():
    status = "PASS" if violations == 0 else f"FAIL ({violations})"
    if violations > 0:
        all_passed = False
    print(f"  {check}: {status}")

print(f"\nOverall: {'ALL PASSED' if all_passed else 'FAILURES DETECTED'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary View

# COMMAND ----------

display(
    spark.sql(f"""
        SELECT summary_date,
               SUM(transaction_count) as total_transactions,
               SUM(total_amount) as total_volume,
               SUM(unique_customers) as total_customers
        FROM {GOLD_TABLE}
        GROUP BY summary_date
        ORDER BY summary_date DESC
        LIMIT 10
    """)
)
