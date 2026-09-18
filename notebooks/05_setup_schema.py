# Databricks notebook source
# MAGIC %md
# MAGIC # Schema Setup
# MAGIC
# MAGIC Creates the Unity Catalog structure for DisasterZero:
# MAGIC - Catalog: `transactions`
# MAGIC - Schemas: `bronze`, `silver`, `gold`, `quarantine`
# MAGIC
# MAGIC Run this once before executing the pipeline.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE CATALOG IF NOT EXISTS transactions;

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG transactions;

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS bronze
# MAGIC COMMENT 'Raw ingested data from landing zone';

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS silver
# MAGIC COMMENT 'Cleaned and validated transaction data';

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS gold
# MAGIC COMMENT 'Business-level aggregated summaries';

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS quarantine
# MAGIC COMMENT 'Rejected records that failed quality validation';

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW SCHEMAS IN transactions;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Quality Audit Table
# MAGIC
# MAGIC Used by the DataTrust Bridge to log quality check results
# MAGIC after each disaster recovery scenario.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS transactions.silver.quality_audit (
# MAGIC     audit_id STRING,
# MAGIC     incident_id STRING,
# MAGIC     rule_id STRING,
# MAGIC     rule_name STRING,
# MAGIC     layer STRING,
# MAGIC     severity STRING,
# MAGIC     violation_count LONG,
# MAGIC     passed BOOLEAN,
# MAGIC     checked_at TIMESTAMP,
# MAGIC     details STRING
# MAGIC )
# MAGIC USING DELTA
# MAGIC COMMENT 'DisasterZero quality gate audit trail';

# COMMAND ----------

print("Schema setup complete.")
print("Catalog: transactions")
print("Schemas: bronze, silver, gold, quarantine")
print("Audit table: transactions.silver.quality_audit")
