# Databricks notebook source
# MAGIC %md
# MAGIC # Sample Data Generator
# MAGIC
# MAGIC Generates realistic transaction data for testing the DisasterZero
# MAGIC pipeline. Writes JSON files to the landing zone for Auto Loader
# MAGIC to pick up.

# COMMAND ----------

import json
import random
import uuid
from datetime import datetime, timedelta

LANDING_ZONE = "/Volumes/transactions/landing/raw/"
NUM_RECORDS = 1000

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

MERCHANTS = [
    "Amazon", "Shoprite", "Woolworths", "Takealot", "Pick n Pay",
    "Checkers", "Clicks", "Dis-Chem", "Mr Price", "Capitec",
]

CATEGORIES = [
    "retail", "groceries", "electronics", "clothing", "healthcare",
    "finance", "entertainment", "travel", "food", "utilities",
]

CURRENCIES = ["ZAR", "USD", "EUR", "GBP"]
STATUSES = ["COMPLETED", "PENDING", "FAILED", "REFUNDED"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate Records

# COMMAND ----------

records = []
base_time = datetime.now() - timedelta(days=30)

for i in range(NUM_RECORDS):
    record = {
        "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
        "customer_id": f"CUST-{random.randint(1000, 9999)}",
        "amount": round(random.uniform(10.0, 50000.0), 2),
        "currency": random.choice(CURRENCIES),
        "status": random.choices(
            STATUSES, weights=[70, 15, 10, 5]
        )[0],
        "merchant": random.choice(MERCHANTS),
        "category": random.choice(CATEGORIES),
        "timestamp": (
            base_time + timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
        ).isoformat(),
    }
    records.append(record)

print(f"Generated {len(records)} records")
print(f"Sample: {json.dumps(records[0], indent=2)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Landing Zone

# COMMAND ----------

batch_size = 100
for i in range(0, len(records), batch_size):
    batch = records[i : i + batch_size]
    batch_num = i // batch_size + 1
    filename = f"{LANDING_ZONE}batch_{batch_num:04d}.json"

    content = "\n".join(json.dumps(r) for r in batch)
    dbutils.fs.put(filename, content, overwrite=True)
    print(f"Wrote {len(batch)} records to {filename}")

print(f"\nDone. {len(records)} records in {batch_num} batches.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify

# COMMAND ----------

files = dbutils.fs.ls(LANDING_ZONE)
print(f"Files in landing zone: {len(files)}")
for f in files[:5]:
    print(f"  {f.name} ({f.size} bytes)")
