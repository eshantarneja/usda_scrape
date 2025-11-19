"""Script to create database tables in Supabase."""
import os
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

# Read the schema SQL file
with open('schema.sql', 'r') as f:
    schema_sql = f.read()

# Initialize Supabase client
client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Creating tables in Supabase...")
print("=" * 60)

# Split the SQL into individual statements
# We need to execute them separately for better error handling
sql_statements = []
current_statement = []

for line in schema_sql.split('\n'):
    # Skip comments and empty lines
    stripped_line = line.strip()
    if not stripped_line or stripped_line.startswith('--'):
        continue

    current_statement.append(line)

    # Check if this is the end of a statement
    if stripped_line.endswith(';'):
        sql_statements.append('\n'.join(current_statement))
        current_statement = []

print(f"Found {len(sql_statements)} SQL statements to execute\n")

# Execute each statement
success_count = 0
failed_count = 0

for i, statement in enumerate(sql_statements, 1):
    # Skip comments-only statements
    if not statement.strip() or all(line.strip().startswith('--') or not line.strip() for line in statement.split('\n')):
        continue

    # Get the first meaningful line for logging
    first_line = next((line.strip() for line in statement.split('\n') if line.strip() and not line.strip().startswith('--')), '')
    action = first_line[:80] + '...' if len(first_line) > 80 else first_line

    try:
        # Execute via Supabase's RPC or direct SQL
        # Note: Supabase client doesn't have direct SQL execution
        # We'll use the postgREST API, but for DDL statements,
        # users should run this in Supabase SQL Editor
        print(f"Statement {i}: {action}")
        print("  ⚠️  Please run the full schema.sql in your Supabase SQL Editor")
        print("     (This script can't execute DDL statements via the API)\n")
        break
    except Exception as e:
        print(f"  ❌ Error: {e}\n")
        failed_count += 1

print("=" * 60)
print("\n📋 INSTRUCTIONS:")
print("=" * 60)
print("The Supabase Python client doesn't support DDL statements (CREATE TABLE, etc.)")
print("Please follow these steps to create the tables:\n")
print("1. Go to your Supabase dashboard: https://supabase.com/dashboard")
print(f"2. Select your project: spmnsezsyzoyobkusvyh")
print("3. Click on 'SQL Editor' in the left sidebar")
print("4. Click 'New query'")
print("5. Copy the entire contents of 'schema.sql' from this repository")
print("6. Paste into the SQL editor")
print("7. Click 'Run' (or press Cmd/Ctrl + Enter)")
print("\nYou should see: 'Success. No rows returned'")
print("Then run this script again to verify the tables were created.")
print("\n" + "=" * 60)
