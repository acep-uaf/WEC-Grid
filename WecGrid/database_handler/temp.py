import sqlite3

DB_PATH = "WEC-GRID.db"

keep_tables = {"WEC_output_1"}
system_tables = {"sqlite_sequence"}  # Do not drop this

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    all_tables = {row[0] for row in cursor.fetchall()}

    # Determine tables to drop (exclude both the one we want to keep and system table)
    drop_tables = all_tables - keep_tables - system_tables

    for table in drop_tables:
        print(f"Dropping table: {table}")
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    conn.commit()