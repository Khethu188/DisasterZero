
"""
databricks/notebooks/verify_pipeline.py
────────────────────────────────────────
Final pipeline verification task.
Runs after Gold layer build to confirm end-to-end data integrity.
DisasterZero also calls these checks independently after recovery.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count

spark = SparkSession.builder.getOrCreate()


# ═══════════════════════════════════════════════════════════════
# Verification Checks
# ═══════════════════════════════════════════════════════════════
class PipelineVerifier:
    """End-to-end pipeline verification."""

    def __init__(self):
        self.results = {}
        self.all_passed = True

    def check(self, name: str, passed: bool, details: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results[name] = {"passed": passed, "details": details}
        if not passed:
            self.all_passed = False
        print(f"  [{status}] {name}" + (f" — {details}" if details else ""))

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results.values() if r["passed"])
        failed = total - passed
        print(f"\n{'='*50}")
        print(f"VERIFICATION SUMMARY: {passed}/{total} passed, {failed} failed")
        print(f"{'='*50}")
        if not self.all_passed:
            raise Exception(
                f"Pipeline verification failed: {failed}/{total} checks failed. "
                f"Failed: {[k for k, v in self.results.items() if not v['passed']]}"
            )
        return self.results


v = PipelineVerifier()
print("Running pipeline verification...\n")


# ── 1. Record Accounting ──
bronze_count = spark.read.table("transactions.bronze.raw_transactions").count()
silver_count = spark.read.table("transactions.silver.processed").count()
quarantine_count = spark.read.table("transactions.quarantine.records").count()
accounted = silver_count + quarantine_count

v.check(
    "Record Accounting",
    bronze_count == accounted,
    f"Bronze={bronze_count:,} | Silver={silver_count:,} + Quarantine={quarantine_count:,} = {accounted:,}"
)


# ── 2. No Duplicates in Silver ──
dup_count = spark.sql("""
    SELECT COUNT(*) FROM (
        SELECT transaction_id, COUNT(*) as cnt
        FROM transactions.silver.processed
        GROUP BY transaction_id
        HAVING cnt > 1
    )
""").collect()[0][0]

v.check("No Duplicates in Silver", dup_count == 0, f"Duplicates found: {dup_count}")


# ── 3. No NULL Required Fields in Silver ──
null_checks = spark.sql("""
    SELECT
        SUM(CASE WHEN transaction_id IS NULL THEN 1 ELSE 0 END) as null_ids,
        SUM(CASE WHEN account_id IS NULL THEN 1 ELSE 0 END) as null_accounts,
        SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) as null_amounts,
        SUM(CASE WHEN currency IS NULL THEN 1 ELSE 0 END) as null_currencies,
        SUM(CASE WHEN timestamp IS NULL THEN 1 ELSE 0 END) as null_timestamps
    FROM transactions.silver.processed
""").collect()[0]

total_nulls = sum(null_checks)
v.check(
    "No NULL Required Fields",
    total_nulls == 0,
    f"NULL ids={null_checks[0]}, accounts={null_checks[1]}, "
    f"amounts={null_checks[2]}, currencies={null_checks[3]}, timestamps={null_checks[4]}"
)


# ── 4. No Negative Amounts in Silver ──
neg_count = spark.sql(
    "SELECT COUNT(*) FROM transactions.silver.processed WHERE amount < 0"
).collect()[0][0]

v.check("No Negative Amounts", neg_count == 0, f"Negative amounts: {neg_count}")


# ── 5. Valid Currencies Only ──
invalid_currency = spark.sql("""
    SELECT COUNT(*) FROM transactions.silver.processed
    WHERE currency NOT IN ('USD', 'EUR', 'GBP', 'ZAR', 'JPY', 'CAD', 'AUD')
""").collect()[0][0]

v.check("Valid Currencies Only", invalid_currency == 0, f"Invalid: {invalid_currency}")


# ── 6. Gold Tables Populated ──
daily_count = spark.read.table("transactions.gold.daily_summary").count()
account_count = spark.read.table("transactions.gold.account_metrics").count()
risk_count = spark.read.table("transactions.gold.risk_scores").count()

v.check("Gold Daily Summary Populated", daily_count > 0, f"Rows: {daily_count}")
v.check("Gold Account Metrics Populated", account_count > 0, f"Rows: {account_count}")
v.check("Gold Risk Scores Populated", risk_count > 0, f"Rows: {risk_count}")


# ── 7. Risk Scores Valid ──
invalid_risk = spark.sql("""
    SELECT COUNT(*) FROM transactions.gold.risk_scores
    WHERE risk_level NOT IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
       OR risk_score < 0
       OR risk_score > 100
""").collect()[0][0]

v.check("Risk Scores Valid", invalid_risk == 0, f"Invalid scores: {invalid_risk}")


# ── 8. Pipeline Health Recorded ──
health_count = spark.read.table("transactions.gold.pipeline_health").count()
v.check("Pipeline Health Recorded", health_count > 0, f"Snapshots: {health_count}")


# ── 9. Data Freshness ──
latest_processed = spark.sql("""
    SELECT MAX(processed_at) FROM transactions.silver.processed
""").collect()[0][0]

v.check(
    "Data Freshness",
    latest_processed is not None,
    f"Latest processed: {latest_processed}"
)


# ── Final Summary ──
v.summary()

