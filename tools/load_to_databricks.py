"""Load the model's 10 tables into Databricks as Delta tables (Step 10b).

Same rows as the embedded model (shared shaping in fmcg_data.py), with snake_case names because
Delta column names can't contain spaces: 'Primary Sales'[Net Primary Value] ->
e2e_dev.fmcg.primary_sales.net_primary_value.

    pandas -> Parquet (local, git-ignored) -> UC volume -> CREATE OR REPLACE TABLE ... AS SELECT

Run from the project root (re-running replaces the tables):
    uv run --no-project --with pandas --with openpyxl --with pyarrow python -I tools/load_to_databricks.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fmcg_data import (DATABRICKS_CATALOG as CATALOG, DATABRICKS_PROFILE as PROFILE,  # noqa: E402
                       DATABRICKS_SCHEMA as SCHEMA, DATABRICKS_WAREHOUSE_ID as WAREHOUSE_ID,
                       ROOT, load_tables, snake)

VOLUME = "raw"
LOCAL_DIR = ROOT / ".databricks_load"  # Parquet files, git-ignored


def run_sql(sql):
    """Run one SQL statement on the warehouse; return the result rows."""
    result = subprocess.run(
        ["databricks", "experimental", "aitools", "tools", "query", sql, "--profile", PROFILE],
        capture_output=True, text=True, env={**os.environ, "DATABRICKS_WAREHOUSE_ID": WAREHOUSE_ID})
    if result.returncode != 0:
        sys.exit(f"SQL failed:\n{sql}\n{result.stderr or result.stdout}")
    # SELECTs print a JSON list of row objects; DDL prints "Query executed successfully (no results)"
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def column_sql(name, dtype):
    """Select-list entry that fixes the Delta type: dates as DATE, money and ratios as DECIMAL."""
    col = f"`{snake(name)}`"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return f"CAST({col} AS DATE) AS {col}"
    if pd.api.types.is_float_dtype(dtype):
        return f"CAST({col} AS DECIMAL(18, 2)) AS {col}"
    if pd.api.types.is_integer_dtype(dtype):
        return f"CAST({col} AS BIGINT) AS {col}"
    return col


tables = load_tables()
LOCAL_DIR.mkdir(exist_ok=True)
volume_path = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

print(f"1. Schema and volume: {CATALOG}.{SCHEMA}, {volume_path}")
run_sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA} COMMENT 'FMCG sales tutorial: source tables for Power BI'")
run_sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME} "
        "COMMENT 'Parquet files exported from the Excel workbook by tools/load_to_databricks.py'")

print("2. Upload Parquet files and create Delta tables")
for name, df in tables.items():
    table = snake(name)
    parquet = LOCAL_DIR / f"{table}.parquet"
    df.rename(columns=snake).to_parquet(parquet, index=False)
    upload = subprocess.run(["databricks", "fs", "cp", str(parquet), f"dbfs:{volume_path}/{table}.parquet",
                             "--overwrite", "--profile", PROFILE], capture_output=True, text=True)
    if upload.returncode != 0:
        sys.exit(f"Upload failed for {parquet.name}: {upload.stderr}")
    select_list = ",\n       ".join(column_sql(c, df[c].dtype) for c in df.columns)
    run_sql(f"""CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.`{table}`
COMMENT 'Model table "{name}", loaded from the Excel workbook by tools/load_to_databricks.py'
AS SELECT {select_list}
FROM read_files('{volume_path}/{table}.parquet', format => 'parquet')""")
    print(f"   {CATALOG}.{SCHEMA}.{table:<16} created")

print("3. Row counts: Databricks vs pandas")
ok = True
for name, df in tables.items():
    table = snake(name)
    rows = run_sql(f"SELECT COUNT(*) AS n FROM {CATALOG}.{SCHEMA}.`{table}`")
    count = int(rows[0]["n"])  # the CLI returns numbers as text
    match = count == len(df)
    ok &= match
    print(f"   {'✅' if match else '❌'} {table:<16} {count:>6} rows (expected {len(df)})")
sys.exit(0 if ok else 1)
