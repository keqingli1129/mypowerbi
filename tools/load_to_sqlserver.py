"""Load the model's 10 tables into SQL Server (Step 13b).

Same rows as the Databricks tables (shared shaping in fmcg_data.py), with the same snake_case names:
'Primary Sales'[Net Primary Value] -> FMCG.fmcg.primary_sales.net_primary_value.

    pandas -> pyodbc (fast_executemany) -> existing tables from tools/sqlserver/create_tables.sql

Everything runs in one transaction: empty all 10 tables, insert, compare row counts and totals with
pandas, and commit only if everything matches (otherwise roll back, leaving the old data).

Run from the project root (re-running replaces the rows):
    uv run --no-project --with pandas --with openpyxl --with pyodbc python -I -X utf8 tools/load_to_sqlserver.py
"""

import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fmcg_data import (SQLSERVER_DATABASE as DATABASE, SQLSERVER_SCHEMA as SCHEMA,  # noqa: E402
                       SQLSERVER_SERVER as SERVER, load_tables, snake)

# Windows sign-in; TrustServerCertificate because a local SQL Server Express has a self-signed certificate
CONNECTION = (f"Driver={{ODBC Driver 18 for SQL Server}};Server={SERVER};Database={DATABASE};"
              "Trusted_Connection=yes;TrustServerCertificate=yes")

# Totals compared with pandas after loading (the guide's quick check)
TOTALS = {"Primary Sales": "Net Primary Value", "Secondary Sales": "Secondary Value"}


def sql_value(value, dtype):
    """pandas value -> pyodbc parameter: dates as date, money as Decimal with 2 places (drops float noise)."""
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return value.date()
    if pd.api.types.is_float_dtype(dtype):
        return Decimal(f"{value:.2f}")
    if pd.api.types.is_integer_dtype(dtype):
        return int(value)
    return str(value)


tables = load_tables()
conn = pyodbc.connect(CONNECTION, autocommit=False)
cur = conn.cursor()
cur.fast_executemany = True

missing = [snake(n) for n in tables if cur.execute("SELECT OBJECT_ID(?, 'U')", f"{SCHEMA}.{snake(n)}").fetchval() is None]
if missing:
    sys.exit(f"Tables missing in {SERVER}/{DATABASE}: {', '.join(missing)}\n"
             "Create them first: sqlcmd -S .\\SQLEXPRESS -E -C -b -i tools/sqlserver/create_tables.sql")

print(f"1. Empty the tables in {SERVER} / {DATABASE}.{SCHEMA}")
for name in tables:
    cur.execute(f"TRUNCATE TABLE {SCHEMA}.[{snake(name)}]")

print("2. Insert rows")
for name, df in tables.items():
    columns = ", ".join(f"[{snake(c)}]" for c in df.columns)
    placeholders = ", ".join("?" for _ in df.columns)
    dtypes = [df[c].dtype for c in df.columns]
    rows = [[sql_value(v, t) for v, t in zip(row, dtypes)] for row in df.itertuples(index=False)]
    cur.executemany(f"INSERT INTO {SCHEMA}.[{snake(name)}] ({columns}) VALUES ({placeholders})", rows)
    print(f"   {SCHEMA}.{snake(name):<16} {len(rows):>6} rows")

print("3. Check: SQL Server vs pandas")
ok = True
for name, df in tables.items():
    count = cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.[{snake(name)}]").fetchval()
    match = count == len(df)
    ok &= match
    print(f"   {'✅' if match else '❌'} {snake(name):<16} {count:>6} rows (expected {len(df)})")
for name, col in TOTALS.items():
    total = cur.execute(f"SELECT SUM([{snake(col)}]) FROM {SCHEMA}.[{snake(name)}]").fetchval()
    expected = Decimal(f"{tables[name][col].sum():.2f}")
    match = total == expected
    ok &= match
    print(f"   {'✅' if match else '❌'} SUM({snake(name)}.{snake(col)}) = {total:,} (expected {expected:,})")

if ok:
    conn.commit()
    print("Committed.")
else:
    conn.rollback()
    print("Rolled back: the tables keep their previous rows.")
conn.close()
sys.exit(0 if ok else 1)
