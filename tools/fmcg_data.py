"""Shared data shaping: turns the Excel workbook into the model's 10 star-schema tables.

Used by build_semantic_model.py (embedded data) and load_to_databricks.py (Delta tables),
so both always contain exactly the same rows and columns.
"""

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "FMCG_Sales_Data_Suraj_Consumer.xlsx"

# Dimension table -> its key column
DIMENSION_KEYS = {"Date": "Date", "Area": "ASM", "Sales Officer": "Sales Officer",
                  "Distributor": "Distributor Code", "Category": "Category", "Product": "SKU Code"}

# (fact table, fact column, dimension): every relationship in the model
RELATIONSHIPS = [
    ("Primary Sales", "Date", "Date"), ("Secondary Sales", "Date", "Date"),
    ("Targets", "Date", "Date"), ("Coverage", "Date", "Date"),
    ("Primary Sales", "ASM", "Area"), ("Secondary Sales", "ASM", "Area"),
    ("Targets", "ASM", "Area"), ("Coverage", "ASM", "Area"),
    ("Primary Sales", "Category", "Category"), ("Secondary Sales", "Category", "Category"),
    ("Targets", "Category", "Category"),
    ("Primary Sales", "Sales Officer", "Sales Officer"), ("Secondary Sales", "Sales Officer", "Sales Officer"),
    ("Coverage", "Sales Officer", "Sales Officer"),
    ("Primary Sales", "Distributor Code", "Distributor"), ("Secondary Sales", "Distributor Code", "Distributor"),
    ("Primary Sales", "SKU Code", "Product"), ("Secondary Sales", "SKU Code", "Product"),
]


def snake(name):
    """Model name -> Databricks name: 'Net Primary Value' -> 'net_primary_value'."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def month_start(month_text):
    """Turn '2025-01' into the date 2025-01-01 so monthly facts can join the Date table."""
    return pd.to_datetime(month_text + "-01")


def load_tables():
    """Read the workbook and return {model table name: DataFrame with model column names}."""
    sheets = pd.read_excel(XLSX, sheet_name=None)
    primary = sheets["Primary_Sales"]
    secondary = sheets["Secondary_Sales"]
    targets = sheets["Targets"]
    coverage = sheets["Coverage_Productivity"]
    products = sheets["Product_Master"]
    distributors = sheets["Distributor_Master"]
    calendar = sheets["Calendar"]

    tables = {
        # Dimensions
        "Date": pd.DataFrame({
            "Date": calendar["Date"],
            "Year": calendar["Year"],
            "Month Number": calendar["Month_No"],
            "Year Month Number": calendar["Year"] * 100 + calendar["Month_No"],
            "Month Name": calendar["Month_Name"],
            "Month": calendar["Date"].dt.strftime("%b"),
            "Quarter": "Q" + calendar["Quarter"].astype(str),
            "Financial Year": calendar["FY"],
        }),
        "Area": (distributors[["Zone", "RSM", "ASM"]].drop_duplicates()
                 .sort_values(["Zone", "RSM", "ASM"]).reset_index(drop=True)),
        "Sales Officer": (distributors[["SO", "ASM"]].drop_duplicates()
                          .rename(columns={"SO": "Sales Officer"})
                          .sort_values("Sales Officer").reset_index(drop=True)),
        "Distributor": distributors[["Distributor_Code", "Distributor_Name", "State", "City"]].rename(
            columns={"Distributor_Code": "Distributor Code", "Distributor_Name": "Distributor"}),
        "Category": pd.DataFrame({"Category": sorted(products["Category"].unique())}),
        "Product": products[["SKU_Code", "Brand", "SKU", "Pack", "MRP", "UnitsPerCase", "PTR", "PTS"]].rename(
            columns={"SKU_Code": "SKU Code", "UnitsPerCase": "Units Per Case"}),
        # Facts: keys + numbers only (descriptive columns live in the dimensions)
        "Primary Sales": pd.DataFrame({
            "Date": primary["Date"],
            "ASM": primary["ASM"],
            "Sales Officer": primary["SO"],
            "Category": primary["Category"],
            "Distributor Code": primary["Distributor_Code"],
            "SKU Code": primary["SKU_Code"],
            "Units": primary["Units"],
            "Gross Value": primary["Gross_Value"],
            "Scheme Discount": primary["Scheme_Discount"].round(2),
            "Net Primary Value": primary["Net_Primary_Value"].round(2),
        }),
        "Secondary Sales": pd.DataFrame({
            "Date": secondary["Date"],
            "ASM": secondary["ASM"],
            "Sales Officer": secondary["SO"],
            "Category": secondary["Category"],
            "Distributor Code": secondary["Distributor_Code"],
            "SKU Code": secondary["SKU_Code"],
            "Channel": secondary["Channel"],
            "Units Sold": secondary["Units_Sold"],
            "Secondary Value": secondary["Secondary_Value"].round(2),
        }),
        "Targets": pd.DataFrame({
            "Date": month_start(targets["Month"]),
            "ASM": targets["ASM"],
            "Category": targets["Category"],
            "Primary Target Value": targets["Primary_Target"],
            "Secondary Target Value": targets["Secondary_Target"],
        }),
        "Coverage": pd.DataFrame({
            "Date": month_start(coverage["Month"]),
            "ASM": coverage["ASM"],
            "Sales Officer": coverage["SO"],
            "Total Outlets": coverage["Total_Outlets"],
            "Outlets Billed": coverage["Outlets_Billed"],
            "Planned Calls": coverage["Planned_Calls"],
            "Productive Calls": coverage["Productive_Calls"],
            "Lines Per Bill": coverage["Avg_Lines_Per_Bill"],
        }),
    }
    validate(tables)
    return tables


def validate(tables):
    """Stop if a dimension key is duplicated or a fact key is missing from its dimension."""
    for name, key in DIMENSION_KEYS.items():
        if tables[name][key].duplicated().any():
            sys.exit(f"Duplicate key in {name}[{key}]")
    for fact, column, dim_name in RELATIONSHIPS:
        missing = set(tables[fact][column]) - set(tables[dim_name][DIMENSION_KEYS[dim_name]])
        if missing:
            sys.exit(f"{fact}[{column}] has values missing from {dim_name}: {sorted(missing)[:5]}")
