"""
Database management module for Smart Routine Generator.
Uses Python's standard library `sqlite3` to manage connections,
schema migrations, and table verification.
"""

import sqlite3
from pathlib import Path
from typing import List, Tuple

# Base directory where this file resides
BASE_DIR = Path(__file__).resolve().parent

# Default paths for SQLite database and schema script
DATABASE_PATH = BASE_DIR / "routine.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

# The six core tables required by the Smart Routine Generator
EXPECTED_TABLES = [
    "subjects",
    "teachers",
    "teacher_subjects",
    "sections",
    "section_requirements",
    "timetable_entries",
]


def get_db_connection(db_path: Path = DATABASE_PATH) -> sqlite3.Connection:
    """
    Establish and return a connection to the SQLite database.

    Key configurations:
    1. `PRAGMA foreign_keys = ON`: SQLite disables foreign key checks by default.
       Enabling this ensures referential integrity (e.g. cascade deletes, valid foreign keys).
    2. `row_factory = sqlite3.Row`: Allows accessing columns both by index and by
       case-insensitive name (e.g., `row['name']`), matching Flask conventions.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DATABASE_PATH, schema_path: Path = SCHEMA_PATH) -> None:
    """
    Initialize the database using the schema defined in schema.sql.
    Creates all tables, relationships, and constraints.
    """
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as schema_file:
        schema_script = schema_file.read()

    conn = get_db_connection(db_path)
    try:
        conn.executescript(schema_script)
        conn.commit()
    finally:
        conn.close()


def get_existing_tables(db_path: Path = DATABASE_PATH) -> List[str]:
    """
    Fetch all user-defined table names currently in the SQLite database.
    Ignores internal SQLite tables (e.g., sqlite_sequence).
    """
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
            """
        )
        rows = cursor.fetchall()
        return [row["name"] for row in rows]
    finally:
        conn.close()


def get_table_columns(table_name: str, db_path: Path = DATABASE_PATH) -> List[Tuple[str, str, bool, bool]]:
    """
    Retrieve column metadata (name, type, notnull, pk) for a given table.
    """
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        return [(col["name"], col["type"], bool(col["notnull"]), bool(col["pk"])) for col in columns]
    finally:
        conn.close()


def verify_tables(db_path: Path = DATABASE_PATH) -> bool:
    """
    Verify that all expected tables exist in the database.
    Prints a detailed inspection table.
    Returns True if all expected tables are found, False otherwise.
    """
    existing = set(get_existing_tables(db_path))
    expected = set(EXPECTED_TABLES)

    print("\n" + "=" * 60)
    print("SMART ROUTINE GENERATOR - DATABASE VERIFICATION")
    print("=" * 60)
    print(f"Database File: {db_path.name}")
    print(f"Full Path:     {db_path}\n")

    all_present = True
    for table in EXPECTED_TABLES:
        status = "[OK] Present" if table in existing else "[FAIL] Missing"
        if table not in existing:
            all_present = False
        print(f"  * {table:<24} -> {status}")

    print("-" * 60)
    if all_present:
        print(f"Status: SUCCESS! All {len(EXPECTED_TABLES)} required tables exist.\n")
        print("Table Details:")
        for table in EXPECTED_TABLES:
            columns = get_table_columns(table, db_path)
            col_summary = ", ".join(
                [f"{col[0]} ({col[1]}{' PK' if col[3] else ''})" for col in columns]
            )
            print(f"  - {table}: {col_summary}")
    else:
        missing = expected - existing
        print(f"Status: ERROR! Missing tables: {', '.join(missing)}")

    print("=" * 60 + "\n")
    return all_present


if __name__ == "__main__":
    print(f"Initializing database at: {DATABASE_PATH} ...")
    init_db()
    print("Database initialized from schema.sql successfully.")
    is_valid = verify_tables()
    if not is_valid:
        exit(1)
