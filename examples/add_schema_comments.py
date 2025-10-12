"""
Example: Add schema comments to existing DuckDB databases.

This script demonstrates how to retrofit self-documentation
(COMMENT ON statements) to existing databases without recreating them.

NO DATA IS RECREATED - this only adds metadata comments!
"""

import exness_data_preprocess as edp
from pathlib import Path

# Initialize processor (default: ~/eon/exness-data/)
processor = edp.ExnessDataProcessor()

# Or specify custom base_dir (must be Path object)
# processor = edp.ExnessDataProcessor(base_dir=Path("~/eon/exness-data"))

# Option 1: Add comments to specific database
print("=== Adding comments to EURUSD database ===")
success = processor.add_schema_comments("EURUSD")

if success:
    print("\n✓ Comments added successfully!")

    # Verify comments were added
    import duckdb
    conn = duckdb.connect(str(processor.base_dir / "eurusd.duckdb"), read_only=True)

    print("\n--- Table Comments ---")
    tables = conn.execute("SELECT table_name, comment FROM duckdb_tables()").df()
    print(tables)

    print("\n--- Column Comments (ohlc_1m) ---")
    columns = conn.execute("""
        SELECT column_name, data_type, comment
        FROM duckdb_columns()
        WHERE table_name = 'ohlc_1m'
        ORDER BY column_index
    """).df()
    print(columns)

    conn.close()

# Option 2: Add comments to ALL databases in base_dir
print("\n\n=== Adding comments to ALL databases ===")
results = processor.add_schema_comments_all()

print("\nResults:")
for pair, success in results.items():
    status = "✓" if success else "✗"
    print(f"  {status} {pair}")

print(f"\nTotal updated: {sum(results.values())} databases")
