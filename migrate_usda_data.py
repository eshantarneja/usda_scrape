"""One-time script to backfill USDA data from prod to dev Supabase branch."""
import os
from supabase import create_client

PROD_URL = os.environ["PROD_SUPABASE_URL"]
PROD_KEY = os.environ["PROD_SUPABASE_KEY"]
DEV_URL = os.environ["DEV_SUPABASE_URL"]
DEV_KEY = os.environ["DEV_SUPABASE_KEY"]

BATCH_SIZE = 500

prod = create_client(PROD_URL, PROD_KEY)
dev = create_client(DEV_URL, DEV_KEY)


def fetch_all(client, table, order_col="id"):
    """Fetch all rows from a table using pagination."""
    all_rows = []
    offset = 0
    while True:
        resp = client.table(table).select("*").order(order_col).range(offset, offset + BATCH_SIZE - 1).execute()
        rows = resp.data
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return all_rows


def insert_batch(client, table, rows):
    """Insert rows in batches."""
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        client.table(table).insert(batch).execute()
        print(f"  Inserted {min(i + BATCH_SIZE, len(rows))}/{len(rows)} rows")


def delete_all(client, table):
    """Delete all rows from a table."""
    client.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()


# Tables in FK-safe order for deletion (children first)
DELETE_ORDER = ["usda_metrics", "usda_prices", "usda_reports", "usda_products"]
# Tables in FK-safe order for insertion (parents first)
INSERT_ORDER = ["usda_products", "usda_reports", "usda_prices", "usda_metrics"]

print("=== Step 1: Clear dev tables ===")
for table in DELETE_ORDER:
    print(f"Deleting {table}...")
    delete_all(dev, table)
    print(f"  Done")

print("\n=== Step 2: Export from prod ===")
data = {}
for table in INSERT_ORDER:
    print(f"Fetching {table}...")
    data[table] = fetch_all(prod, table)
    print(f"  Got {len(data[table])} rows")

print("\n=== Step 3: Insert into dev ===")
for table in INSERT_ORDER:
    rows = data[table]
    if not rows:
        print(f"Skipping {table} (no rows)")
        continue
    print(f"Inserting {table} ({len(rows)} rows)...")
    insert_batch(dev, table, rows)

print("\n=== Step 4: Verify ===")
for table in INSERT_ORDER:
    count = len(fetch_all(dev, table))
    expected = len(data[table])
    status = "OK" if count == expected else f"MISMATCH (expected {expected})"
    print(f"  {table}: {count} rows - {status}")

print("\nDone!")
