
"""
databricks/notebooks/generate_sample_data.py
─────────────────────────────────────────────
Generates realistic financial transaction data for testing.
Run this once to populate the S3 raw layer before running the pipeline.
"""

import json
import random
import uuid
from datetime import datetime, timedelta

# ── Configuration ──
NUM_RECORDS = 20_000
NUM_ACCOUNTS = 500
OUTPUT_PATH = "/dbfs/mnt/disasterzero-data/raw/transactions/"
# Or for S3 direct: "s3://disasterzero-data/raw/transactions/"

# ── Reference Data ──
MERCHANTS = [
    "Amazon", "Walmart", "Shoprite", "Pick n Pay", "Woolworths",
    "Takealot", "Netflix", "Spotify", "Uber", "Bolt",
    "Shell", "Engen", "Checkers", "Spar", "Mr Price",
    "Game", "Makro", "Clicks", "Dis-Chem", "FNB Insurance",
    "Old Mutual", "Discovery", "Vodacom", "MTN", "Eskom",
]

CATEGORIES = [
    "Groceries", "Entertainment", "Transport", "Fuel",
    "Insurance", "Utilities", "Clothing", "Electronics",
    "Healthcare", "Dining", "Travel", "Subscriptions",
]

CURRENCIES = ["ZAR", "USD", "EUR", "GBP"]
CURRENCY_WEIGHTS = [0.70, 0.15, 0.10, 0.05]  # Mostly ZAR

STATUSES = ["COMPLETED", "PENDING", "REVERSED", "DECLINED"]
STATUS_WEIGHTS = [0.85, 0.05, 0.05, 0.05]


def generate_account_ids(n: int) -> list:
    """Generate realistic account IDs."""
    return [f"ACC-{str(i).zfill(6)}" for i in range(1, n + 1)]


def generate_transaction(account_id: str, base_time: datetime) -> dict:
    """Generate a single realistic transaction."""
    merchant = random.choice(MERCHANTS)
    category = random.choice(CATEGORIES)
    currency = random.choices(CURRENCIES, weights=CURRENCY_WEIGHTS, k=1)[0]
    status = random.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]

    # Amount distribution: mostly small, some medium, few large
    amount_type = random.random()
    if amount_type < 0.60:
        amount = round(random.uniform(10, 500), 2)        # Small
    elif amount_type < 0.85:
        amount = round(random.uniform(500, 5000), 2)      # Medium
    elif amount_type < 0.95:
        amount = round(random.uniform(5000, 50000), 2)    # Large
    else:
        amount = round(random.uniform(50000, 250000), 2)  # XLarge

    # Adjust for currency (ZAR amounts are ~18x USD)
    if currency == "ZAR":
        amount = round(amount * random.uniform(15, 20), 2)

    # Random timestamp within the last 30 days
    offset = timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    timestamp = base_time - offset

    return {
        "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
        "account_id": account_id,
        "amount": amount,
        "currency": currency,
        "merchant": merchant,
        "category": category,
        "timestamp": timestamp.isoformat(),
        "status": status,
    }


def inject_anomalies(transactions: list, anomaly_rate: float = 0.02) -> list:
    """
    Inject realistic data quality issues for DataTrust/DisasterZero to catch.
    ~2% of records will have issues.
    """
    num_anomalies = int(len(transactions) * anomaly_rate)
    anomaly_indices = random.sample(range(len(transactions)), num_anomalies)

    anomaly_types = [
        "null_amount",
        "negative_amount",
        "invalid_currency",
        "null_account",
        "extreme_amount",
        "null_timestamp",
    ]

    for idx in anomaly_indices:
        anomaly = random.choice(anomaly_types)
        txn = transactions[idx]

        if anomaly == "null_amount":
            txn["amount"] = None
        elif anomaly == "negative_amount":
            txn["amount"] = -abs(txn["amount"])
        elif anomaly == "invalid_currency":
            txn["currency"] = random.choice(["XXX", "ABC", "123", "", None])
        elif anomaly == "null_account":
            txn["account_id"] = None
        elif anomaly == "extreme_amount":
            txn["amount"] = round(random.uniform(5_000_000, 99_999_999), 2)
        elif anomaly == "null_timestamp":
            txn["timestamp"] = None

    return transactions


def inject_duplicates(transactions: list, dup_rate: float = 0.01) -> list:
    """Inject duplicate records for deduplication testing."""
    num_dups = int(len(transactions) * dup_rate)
    dups = random.sample(transactions, num_dups)
    transactions.extend(dups)
    random.shuffle(transactions)
    return transactions


# ═══════════════════════════════════════════════════════════════
# Generate
# ═══════════════════════════════════════════════════════════════
print(f"Generating {NUM_RECORDS:,} transactions for {NUM_ACCOUNTS} accounts...")

accounts = generate_account_ids(NUM_ACCOUNTS)
base_time = datetime.utcnow()

transactions = []
for _ in range(NUM_RECORDS):
    account = random.choice(accounts)
    txn = generate_transaction(account, base_time)
    transactions.append(txn)

# Inject data quality issues
transactions = inject_anomalies(transactions, anomaly_rate=0.02)
transactions = inject_duplicates(transactions, dup_rate=0.01)

print(f"Total records (with anomalies + duplicates): {len(transactions):,}")

# ═══════════════════════════════════════════════════════════════
# Write to S3 / DBFS as JSON files (batched)
# ═══════════════════════════════════════════════════════════════
BATCH_SIZE = 5000

for i in range(0, len(transactions), BATCH_SIZE):
    batch = transactions[i:i + BATCH_SIZE]
    batch_num = i // BATCH_SIZE + 1
    filename = f"{OUTPUT_PATH}transactions_batch_{batch_num:03d}.json"

    # Write as newline-delimited JSON (Spark-friendly)
    with open(filename, "w") as f:
        for txn in batch:
            f.write(json.dumps(txn) + "\n")

    print(f"  Written batch {batch_num}: {len(batch):,} records → {filename}")

print(f"\n✓ Done! {len(transactions):,} records written to {OUTPUT_PATH}")
print(f"  Anomalies injected: ~{int(NUM_RECORDS * 0.02):,}")
print(f"  Duplicates injected: ~{int(NUM_RECORDS * 0.01):,}")

