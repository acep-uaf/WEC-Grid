import sqlite3

DB_PATH = "./WEC-GRID.db"

# Tables you want to keep
keep_tables = {"WEC_output_1"}

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()

    # Fetch all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}

    # Determine tables to drop
    drop_tables = tables - keep_tables

    # Drop each table
    for table in drop_tables:
        print(f"Dropping table: {table}")
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    conn.commit()