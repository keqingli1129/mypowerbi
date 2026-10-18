"""Compare measures in the published model with values computed independently from the Excel file.

Expected values come straight from the raw sheets with pandas (not from the model-building code),
actual values come from DAX queries against the published model in My workspace.

Run from the project root (after tools/publish_model.py):
    uv run --no-project --with pandas --with openpyxl python -I tools/check_measures.py
"""

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fabric  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
env = dict(line.split("=", 1) for line in (ROOT / "tools" / ".published.env").read_text().split())
QUERY_URL = fabric.dataset_url(env["SEMANTIC_MODEL_ID"]) + "/executeQueries"


def dax(query):
    """Run a DAX query; return rows as dicts keyed by plain column names."""
    _, _, body = fabric.call("POST", QUERY_URL, {"queries": [{"query": query}],
                                                 "serializerSettings": {"includeNulls": True}})
    result = body["results"][0]
    if "error" in result:
        raise RuntimeError(result["error"])
    return [{k.split("[")[-1].rstrip("]"): v for k, v in row.items()} for row in result["tables"][0]["rows"]]


# ---------------------------------------------------------------------------
# Expected values from the raw Excel sheets
# ---------------------------------------------------------------------------
x = pd.read_excel(ROOT / "data" / "FMCG_Sales_Data_Suraj_Consumer.xlsx", sheet_name=None)
p, s, t, c = x["Primary_Sales"], x["Secondary_Sales"], x["Targets"], x["Coverage_Productivity"]
zone_of_asm = x["Distributor_Master"].drop_duplicates("ASM").set_index("ASM")["Zone"]

expected = {
    "Primary Sales": p.Net_Primary_Value.sum(),
    "Primary Units": p.Units.sum(),
    "Secondary Sales": s.Secondary_Value.sum(),
    "Secondary Units": s.Units_Sold.sum(),
    "Sell-Through %": s.Units_Sold.sum() / p.Units.sum(),
    "Primary Target": t.Primary_Target.sum(),
    "Secondary Target": t.Secondary_Target.sum(),
    "Primary Achievement %": p.Net_Primary_Value.sum() / t.Primary_Target.sum(),
    "Secondary Achievement %": s.Secondary_Value.sum() / t.Secondary_Target.sum(),
    "Primary Gap to Target": p.Net_Primary_Value.sum() - t.Primary_Target.sum(),
    "Scheme Spend %": p.Scheme_Discount.sum() / p.Gross_Value.sum(),
    "Numeric Distribution %": c.Outlets_Billed.sum() / c.Total_Outlets.sum(),
    "Productive Call %": c.Productive_Calls.sum() / c.Planned_Calls.sum(),
    "Avg Lines per Bill": (c.Avg_Lines_Per_Bill * c.Outlets_Billed).sum() / c.Outlets_Billed.sum(),
    "Pipeline Stock Units": p.Units.sum() - s.Units_Sold.sum(),
}

h1 = lambda df: df[df.Date.dt.month <= 6]  # Jan-Jun, the only months both years have
prim_by_year = h1(p).groupby(h1(p).Date.dt.year).Net_Primary_Value.sum()
sec_by_year = h1(s).groupby(h1(s).Date.dt.year).Secondary_Value.sum()
expected_2026 = {
    "Primary Sales PY": prim_by_year[2025],
    "Primary YoY %": prim_by_year[2026] / prim_by_year[2025] - 1,
    "Secondary YoY %": sec_by_year[2026] / sec_by_year[2025] - 1,
}

zone_sales = p.groupby("Zone").Net_Primary_Value.sum()
zone_target = t.assign(Zone=t.ASM.map(zone_of_asm)).groupby("Zone").Primary_Target.sum()
expected_zone = (zone_sales / zone_target).to_dict()

cat_sales = s.groupby("Category").Secondary_Value.sum()
expected_mix = (cat_sales / cat_sales.sum()).to_dict()

dec_2025 = pd.Timestamp("2025-12-31")
expected_stock_dec_2025 = p[p.Date <= dec_2025].Units.sum() - s[s.Date <= dec_2025].Units_Sold.sum()

# ---------------------------------------------------------------------------
# Actual values from the model, compared
# ---------------------------------------------------------------------------
results = []


def check(label, actual, want, tolerance=1e-6):
    if want is None:
        ok = actual is None
    else:
        ok = actual is not None and math.isclose(actual, want, rel_tol=tolerance, abs_tol=0.01)
    results.append(ok)
    fmt = lambda v: "blank" if v is None else (f"{v:,.4f}" if abs(v) < 10 else f"{v:,.2f}")
    print(f"  {'✅' if ok else '❌'} {label:<42} model {fmt(actual):>18}   expected {fmt(want):>18}")


print("A. Grand totals (no filters)")
row = dax("EVALUATE ROW(" + ", ".join(f'"{m}", [{m}]' for m in expected) + ")")[0]
for measure, want in expected.items():
    check(measure, row[measure], want)

print("B. Time intelligence by year")
years = {r["Year"]: r for r in dax(
    "EVALUATE SUMMARIZECOLUMNS('Date'[Year], \"Primary Sales PY\", [Primary Sales PY], "
    "\"Primary YoY %\", [Primary YoY %], \"Secondary YoY %\", [Secondary YoY %])")}
for measure, want in expected_2026.items():
    check(f"2026 {measure}", years[2026][measure], want)
# SUMMARIZECOLUMNS drops rows where every measure is blank, so a missing 2025 row means "blank"
check("2025 Primary Sales PY (no 2024 data)", years.get(2025, {}).get("Primary Sales PY"), None)
check("No year selected: Primary YoY %", dax('EVALUATE ROW("v", [Primary YoY %])')[0]["v"], None)

print("C. Achievement by zone (Area filters both sales and targets)")
for r in dax("EVALUATE SUMMARIZECOLUMNS(Area[Zone], \"Ach\", [Primary Achievement %])"):
    check(f"{r['Zone']} Primary Achievement %", r["Ach"], expected_zone[r["Zone"]])

print("D. Category mix")
for r in dax("EVALUATE SUMMARIZECOLUMNS(Category[Category], \"Mix\", [Category Mix %])"):
    check(f"{r['Category']} Category Mix %", r["Mix"], expected_mix[r["Category"]])

print("E. Cumulative stock at a point in time")
stock = dax("EVALUATE CALCULATETABLE(ROW(\"v\", [Pipeline Stock Units]), 'Date'[Year] = 2025)")[0]["v"]
check("Pipeline Stock Units at end of 2025", stock, expected_stock_dec_2025)

print("F. Report helper measures (text and colors) for 2026")
p26, s26 = p[p.Date.dt.year == 2026], s[s.Date.dt.year == 2026]
t26 = t[t.Month.str.startswith("2026")]
gap = p26.Net_Primary_Value.sum() - t26.Primary_Target.sum()
added = p26.Units.sum() - s26.Units_Sold.sum()
arrow = lambda v: "▲ " if v >= 0 else "▼ "
expected_text = {
    "Primary Sales Context": f"{arrow(expected_2026['Primary YoY %'])}{abs(expected_2026['Primary YoY %']):.1%} vs last year",
    "Secondary Sales Context": f"{arrow(expected_2026['Secondary YoY %'])}{abs(expected_2026['Secondary YoY %']):.1%} vs last year",
    "Achievement Context": f"{arrow(gap)}₹{abs(gap) / 1e6:.1f}M {'above' if gap >= 0 else 'below'} target",
    "Sell-Through Context": f"{1 - s26.Units_Sold.sum() / p26.Units.sum():.1%} of units still with distributors",
    "Pipeline Stock Context": f"{arrow(added)}{abs(added):,} units added this period",
    "Achievement Color": "#1A7F37" if gap >= 0 else "#C62828",
    "Primary YoY Color": "#1A7F37" if expected_2026["Primary YoY %"] >= 0 else "#C62828",
}
row26 = dax("EVALUATE CALCULATETABLE(ROW(" + ", ".join(f'"{m}", [{m}]' for m in expected_text)
            + "), 'Date'[Year] = 2026)")[0]
for measure, want in expected_text.items():
    ok = row26[measure] == want
    results.append(ok)
    print(f"  {'✅' if ok else '❌'} {measure:<42} model {row26[measure]!r}   expected {want!r}")

print("G. Last refreshed text (from the Refresh Info table)")
text = dax('EVALUATE ROW("v", [Last Refreshed Text])')[0]["v"] or ""
try:
    refreshed = pd.to_datetime(text.removeprefix("Data refreshed ").removesuffix(" UTC"), format="%d %b %Y %H:%M")
    age_hours = (pd.Timestamp.now("UTC").tz_localize(None) - refreshed).total_seconds() / 3600
    ok = 0 <= age_hours < 48   # refreshed within the last two days (daily schedule)
except ValueError:
    age_hours, ok = None, False
results.append(ok)
age = "unparseable" if age_hours is None else f"{age_hours:.1f} h ago"
print(f"  {'✅' if ok else '❌'} {'Last Refreshed Text':<42} model {text!r} ({age})")

print(f"\n{sum(results)} of {len(results)} checks passed.")
sys.exit(0 if all(results) else 1)
