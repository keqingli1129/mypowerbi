"""Build the FMCG_Sales semantic model (TMDL files).

Three data sources for the same model (only the table partitions, parameters and sourceColumn names differ):
  --source databricks (default)  partitions read the Delta tables in Databricks (Step 10);
                                 the Service needs Databricks credentials to refresh
  --source sqlserver             partitions read the SQL Server tables (Step 13); the Service needs an
                                 on-premises data gateway to refresh
  --source embedded              rows embedded in each partition as compressed JSON (Steps 4-9);
                                 refreshes without any credentials or gateway

Run from the project root:
    uv run --no-project --with pandas --with openpyxl python -I tools/build_semantic_model.py [--source sqlserver|embedded]
"""

import argparse
import base64
import json
import sys
import zlib
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fmcg_data import (DATABRICKS_CATALOG, DATABRICKS_HOST, DATABRICKS_HTTP_PATH,  # noqa: E402
                       DATABRICKS_SCHEMA, DIMENSION_KEYS, RELATIONSHIPS, SQLSERVER_DATABASE,
                       SQLSERVER_SCHEMA, SQLSERVER_SERVER, load_tables, snake)

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--source", choices=["databricks", "sqlserver", "embedded"], default="databricks")
SOURCE = parser.parse_args().source

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "FMCG_Sales.SemanticModel"
DEF_DIR = MODEL_DIR / "definition"

# ---------------------------------------------------------------------------
# 1. The 10 star-schema tables (Step 2 design), shaped in tools/fmcg_data.py
# ---------------------------------------------------------------------------

data = load_tables()

# ---------------------------------------------------------------------------
# 2. Measures (Step 3)
# ---------------------------------------------------------------------------


GOOD, BAD = "#1A7F37", "#C62828"  # green / red used for conditional formatting in the report


def growth_context(prefix):
    """Report helper: KPI context line such as '▲ 9.4% vs last year'."""
    return {"name": f"{prefix} Sales Context", "folder": "Report Helpers", "format": None,
            "description": f"Text under the {prefix.lower()} sales KPI: growth vs last year.",
            "dax": f"""
VAR Growth = [{prefix} YoY %]
RETURN
    IF (
        ISBLANK ( Growth ),
        "No prior-year data",
        IF ( Growth >= 0, "▲ ", "▼ " ) & FORMAT ( ABS ( Growth ), "0.0%" ) & " vs last year"
    )"""}


def time_intelligence(prefix):
    """PY, YoY %, PM and MoM % measures for 'Primary' or 'Secondary' sales."""
    base = f"{prefix} Sales"
    return [
        {"name": f"{base} PY", "folder": "Time Intelligence", "format": "₹#,##0",
         "description": f"{base} for the same period last year. Blank unless one year is in context (data starts in Jan 2025).",
         "dax": f"""
IF (
    HASONEVALUE ( 'Date'[Year] ),
    CALCULATE ( [{base}], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )
)"""},
        {"name": f"{prefix} YoY %", "folder": "Time Intelligence", "format": "+0.0%;-0.0%;0.0%",
         "description": f"Growth of {base.lower()} vs the same period last year.",
         "dax": f"""
VAR PriorYear = [{base} PY]
RETURN
    IF ( NOT ISBLANK ( PriorYear ), DIVIDE ( [{base}] - PriorYear, PriorYear ) )"""},
        {"name": f"{base} PM", "folder": "Time Intelligence", "format": "₹#,##0",
         "description": f"{base} for the previous month.",
         "dax": f"CALCULATE ( [{base}], DATEADD ( 'Date'[Date], -1, MONTH ) )"},
        {"name": f"{prefix} MoM %", "folder": "Time Intelligence", "format": "+0.0%;-0.0%;0.0%",
         "description": f"Growth of {base.lower()} vs the previous month.",
         "dax": f"""
VAR PriorMonth = [{base} PM]
RETURN
    IF ( NOT ISBLANK ( PriorMonth ), DIVIDE ( [{base}] - PriorMonth, PriorMonth ) )"""},
    ]


measures = {
    "Primary Sales": [
        {"name": "Primary Sales", "folder": "Core", "format": "₹#,##0",
         "description": "Net value invoiced to distributors (sell-in), after scheme discount.",
         "dax": "SUM ( 'Primary Sales'[Net Primary Value] )"},
        {"name": "Primary Units", "folder": "Core", "format": "#,##0",
         "description": "Units invoiced to distributors (sell-in).",
         "dax": "SUM ( 'Primary Sales'[Units] )"},
        {"name": "Scheme Spend %", "folder": "Trade Spend", "format": "0.0%",
         "description": "Scheme (trade promotion) discount as a share of gross primary value.",
         "dax": "DIVIDE ( SUM ( 'Primary Sales'[Scheme Discount] ), SUM ( 'Primary Sales'[Gross Value] ) )"},
        growth_context("Primary"),
        {"name": "Primary YoY Color", "folder": "Report Helpers", "format": None,
         "description": "Green when sell-in grew vs last year, red when it fell; used for conditional formatting.",
         "dax": f"""
VAR Growth = [Primary YoY %]
RETURN
    IF ( NOT ISBLANK ( Growth ), IF ( Growth >= 0, "{GOOD}", "{BAD}" ) )"""},
    ] + time_intelligence("Primary"),
    "Secondary Sales": [
        {"name": "Secondary Sales", "folder": "Core", "format": "₹#,##0",
         "description": "Value sold by distributors to retailers (sell-out).",
         "dax": "SUM ( 'Secondary Sales'[Secondary Value] )"},
        {"name": "Secondary Units", "folder": "Core", "format": "#,##0",
         "description": "Units sold by distributors to retailers (sell-out).",
         "dax": "SUM ( 'Secondary Sales'[Units Sold] )"},
        {"name": "Sell-Through %", "folder": "Pipeline", "format": "0.0%",
         "description": "Secondary units ÷ primary units: how much of what was sold in actually moved to retailers.",
         "dax": "DIVIDE ( [Secondary Units], [Primary Units] )"},
        {"name": "Pipeline Stock Units", "folder": "Pipeline", "format": "#,##0",
         "description": "Cumulative primary minus secondary units, from the start of the data to the last selected date.",
         "dax": """
VAR CutoffDate = MAX ( 'Date'[Date] )
RETURN
    CALCULATE (
        [Primary Units] - [Secondary Units],
        REMOVEFILTERS ( 'Date' ),
        'Date'[Date] <= CutoffDate
    )"""},
        {"name": "Category Mix %", "folder": "Core", "format": "0.0%",
         "description": "This category's share of secondary sales within the current filters.",
         "dax": "DIVIDE ( [Secondary Sales], CALCULATE ( [Secondary Sales], REMOVEFILTERS ( Category ) ) )"},
        growth_context("Secondary"),
        {"name": "Sell-Through Context", "folder": "Report Helpers", "format": None,
         "description": "Text under the sell-through KPI: share of units not yet sold on to retailers.",
         "dax": """
VAR SellThrough = [Sell-Through %]
RETURN
    IF ( NOT ISBLANK ( SellThrough ), FORMAT ( 1 - SellThrough, "0.0%" ) & " of units still with distributors" )"""},
        {"name": "Pipeline Stock Context", "folder": "Report Helpers", "format": None,
         "description": "Text under the distributor stock KPI: units added to stock in the selected period.",
         "dax": """
VAR Added = [Primary Units] - [Secondary Units]
RETURN
    IF (
        NOT ISBLANK ( Added ),
        IF ( Added >= 0, "▲ ", "▼ " ) & FORMAT ( ABS ( Added ), "#,##0" ) & " units added this period"
    )"""},
    ] + time_intelligence("Secondary"),
    "Targets": [
        {"name": "Primary Target", "folder": "Targets", "format": "₹#,##0",
         "description": "Primary (sell-in) target, set per ASM × Category × Month.",
         "dax": "SUM ( Targets[Primary Target Value] )"},
        {"name": "Secondary Target", "folder": "Targets", "format": "₹#,##0",
         "description": "Secondary (sell-out) target, set per ASM × Category × Month.",
         "dax": "SUM ( Targets[Secondary Target Value] )"},
        {"name": "Primary Achievement %", "folder": "Achievement", "format": "0.0%",
         "description": "Primary sales ÷ primary target.",
         "dax": "DIVIDE ( [Primary Sales], [Primary Target] )"},
        {"name": "Secondary Achievement %", "folder": "Achievement", "format": "0.0%",
         "description": "Secondary sales ÷ secondary target.",
         "dax": "DIVIDE ( [Secondary Sales], [Secondary Target] )"},
        {"name": "Primary Gap to Target", "folder": "Achievement", "format": "₹#,##0",
         "description": "Primary sales minus primary target; negative means behind target.",
         "dax": """
VAR TargetValue = [Primary Target]
RETURN
    IF ( NOT ISBLANK ( TargetValue ), [Primary Sales] - TargetValue )"""},
        {"name": "Achievement Context", "folder": "Report Helpers", "format": None,
         "description": "Text under the % of target KPI: rupee gap to the primary target.",
         "dax": """
VAR Gap = [Primary Gap to Target]
RETURN
    IF (
        ISBLANK ( Gap ),
        "No target set",
        IF ( Gap >= 0, "▲ ₹", "▼ ₹" ) & FORMAT ( ABS ( Gap ) / 1000000, "0.0" ) & "M "
            & IF ( Gap >= 0, "above", "below" ) & " target"
    )"""},
        {"name": "Achievement Color", "folder": "Report Helpers", "format": None,
         "description": "Green at or above 100% of primary target, red below; used for conditional formatting.",
         "dax": f"""
VAR Achievement = [Primary Achievement %]
RETURN
    IF ( NOT ISBLANK ( Achievement ), IF ( Achievement >= 1, "{GOOD}", "{BAD}" ) )"""},
    ],
    "Coverage": [
        {"name": "Numeric Distribution %", "folder": "Coverage", "format": "0.0%",
         "description": "Outlets billed ÷ total outlets: width of retail reach.",
         "dax": "DIVIDE ( SUM ( Coverage[Outlets Billed] ), SUM ( Coverage[Total Outlets] ) )"},
        {"name": "Productive Call %", "folder": "Coverage", "format": "0.0%",
         "description": "Productive calls ÷ planned calls: salesman efficiency on the beat.",
         "dax": "DIVIDE ( SUM ( Coverage[Productive Calls] ), SUM ( Coverage[Planned Calls] ) )"},
        {"name": "Avg Lines per Bill", "folder": "Coverage", "format": "0.0",
         "description": "Average SKUs per bill, weighted by outlets billed.",
         "dax": """
DIVIDE (
    SUMX ( Coverage, Coverage[Lines Per Bill] * Coverage[Outlets Billed] ),
    SUM ( Coverage[Outlets Billed] )
)"""},
    ],
    "Refresh Info": [
        {"name": "Last Refreshed Text", "folder": "Report Helpers", "format": None,
         "description": "Footer text with the time of the last successful model refresh (UTC).",
         "dax": """
VAR LastRefresh = MAX ( 'Refresh Info'[Last Refreshed] )
RETURN
    IF ( NOT ISBLANK ( LastRefresh ), "Data refreshed " & FORMAT ( LastRefresh, "dd mmm yyyy hh:nn" ) & " UTC" )"""},
    ],
}

# ---------------------------------------------------------------------------
# 3. Columns per table: (name, data type, options)
# ---------------------------------------------------------------------------

HIDDEN = {"hidden": True}
REFRESH_TABLE = "Refresh Info"  # utility table, not in fmcg_data: one row with the refresh time
columns = {
    REFRESH_TABLE: [("Last Refreshed", "dateTime", {"hidden": True, "format": "dd mmm yyyy hh:nn"})],
    "Date": [
        ("Date", "dateTime", {"key": True, "format": "dd mmm yyyy"}),
        ("Year", "int64", {"format": "0"}),
        ("Month Number", "int64", HIDDEN),
        ("Year Month Number", "int64", HIDDEN),
        ("Month Name", "string", {"sort_by": "Year Month Number"}),
        ("Month", "string", {"sort_by": "Month Number"}),
        ("Quarter", "string", {}),
        ("Financial Year", "string", {}),
    ],
    "Area": [("Zone", "string", {}), ("RSM", "string", {}), ("ASM", "string", {"key": True})],
    "Sales Officer": [("Sales Officer", "string", {"key": True}), ("ASM", "string", {})],
    "Distributor": [
        ("Distributor Code", "string", {"key": True, "hidden": True}),
        ("Distributor", "string", {}),
        ("State", "string", {"category": "StateOrProvince"}),
        ("City", "string", {"category": "City"}),
    ],
    "Category": [("Category", "string", {"key": True})],
    "Product": [
        ("SKU Code", "string", {"key": True, "hidden": True}),
        ("Brand", "string", {}), ("SKU", "string", {}), ("Pack", "string", {}),
        ("MRP", "decimal", {"format": "₹#,##0.00"}),
        ("Units Per Case", "int64", {}),
        ("PTR", "decimal", {"format": "₹#,##0.00"}),
        ("PTS", "decimal", {"format": "₹#,##0.00"}),
    ],
    "Primary Sales": [(c, t, HIDDEN) for c, t in [
        ("Date", "dateTime"), ("ASM", "string"), ("Sales Officer", "string"), ("Category", "string"),
        ("Distributor Code", "string"), ("SKU Code", "string"), ("Units", "int64"),
        ("Gross Value", "decimal"), ("Scheme Discount", "decimal"), ("Net Primary Value", "decimal")]],
    "Secondary Sales": [(c, t, HIDDEN) for c, t in [
        ("Date", "dateTime"), ("ASM", "string"), ("Sales Officer", "string"), ("Category", "string"),
        ("Distributor Code", "string"), ("SKU Code", "string")]]
        + [("Channel", "string", {})]
        + [(c, t, HIDDEN) for c, t in [("Units Sold", "int64"), ("Secondary Value", "decimal")]],
    "Targets": [(c, t, HIDDEN) for c, t in [
        ("Date", "dateTime"), ("ASM", "string"), ("Category", "string"),
        ("Primary Target Value", "int64"), ("Secondary Target Value", "int64")]],
    "Coverage": [(c, t, HIDDEN) for c, t in [
        ("Date", "dateTime"), ("ASM", "string"), ("Sales Officer", "string"),
        ("Total Outlets", "int64"), ("Outlets Billed", "int64"), ("Planned Calls", "int64"),
        ("Productive Calls", "int64"), ("Lines Per Bill", "decimal")]],
}

descriptions = {
    "Date": "Calendar, one row per day from 1 Jan 2025 to 30 Jun 2026.",
    "Area": "Sales areas at area sales manager (ASM) grain, with regional sales manager (RSM) and zone.",
    "Sales Officer": "Sales officers (SO) and the ASM they report to.",
    "Distributor": "Distributors and their location.",
    "Category": "Product categories, shared by sales and targets.",
    "Product": "Products at SKU grain with list prices (MRP, PTR = price to retailer, PTS = price to stockist).",
    "Primary Sales": "Primary (sell-in) invoice lines from the company to distributors.",
    "Secondary Sales": "Secondary (sell-out) sales from distributors to retailers, per distributor × SKU × channel × month.",
    "Targets": "Monthly primary and secondary targets per ASM × Category (dated the first of the month).",
    "Coverage": "Monthly outlet coverage and call productivity per sales officer × city (dated the first of the month).",
    REFRESH_TABLE: "One row holding the time of the last model refresh (computed by Power Query during refresh).",
}

# ---------------------------------------------------------------------------
# 4. Write TMDL
# ---------------------------------------------------------------------------

M_TYPES = {"string": "type text", "int64": "Int64.Type", "decimal": "Currency.Type", "dateTime": "type date"}


def q(name):
    """Quote a TMDL object name when it contains spaces or special characters."""
    return f"'{name}'" if any(ch in name for ch in " .=:'-%&()") else name


def embedded_rows(df, cols):
    """M expression that rebuilds the table from compressed JSON embedded in the file."""
    rows = []
    for record in df[[c for c, _, _ in cols]].itertuples(index=False):
        row = []
        for value, (_, dtype, _) in zip(record, cols):
            if dtype == "dateTime":
                row.append(pd.Timestamp(value).strftime("%Y-%m-%d"))
            elif dtype == "int64":
                row.append(int(value))
            elif dtype == "decimal":
                row.append(float(value))
            else:
                row.append(str(value))
        rows.append(row)
    raw = json.dumps(rows, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    deflate = zlib.compressobj(9, zlib.DEFLATED, -15)  # raw deflate, as Power Query expects
    payload = base64.b64encode(deflate.compress(raw) + deflate.flush()).decode("ascii")
    names = ", ".join(f'"{c}"' for c, _, _ in cols)
    types = ", ".join(f'{{"{c}", {M_TYPES[t]}}}' for c, t, _ in cols)
    return [
        "let",
        "\t// Rows are embedded as compressed JSON, so no external data source is needed",
        f'\t#"Decoded Rows" = Json.Document(Binary.Decompress(Binary.FromText("{payload}", BinaryEncoding.Base64), Compression.Deflate)),',
        f'\t#"Built Table" = Table.FromRows(#"Decoded Rows", {{{names}}}),',
        f'\t#"Set Column Types" = Table.TransformColumnTypes(#"Built Table", {{{types}}}, "en-US")',
        "in",
        '\t#"Set Column Types"',
    ]


def databricks_rows(name):
    """M expression that reads the table from Databricks, using the model's connection parameters."""
    return [
        "let",
        "\t// Azure Databricks connector: warehouse -> catalog -> schema -> table",
        '\tSource = Databricks.Catalogs(#"Databricks Host", #"Databricks HTTP Path", [Catalog = null, Database = null]),',
        '\tCatalog = Source{[Name = #"Databricks Catalog", Kind = "Database"]}[Data],',
        '\tSchema = Catalog{[Name = #"Databricks Schema", Kind = "Schema"]}[Data],',
        f'\tTable = Schema{{[Name = "{snake(name)}", Kind = "Table"]}}[Data]',
        "in",
        "\tTable",
    ]


def sqlserver_rows(name):
    """M expression that reads the table from SQL Server, using the model's connection parameters."""
    return [
        "let",
        "\t// SQL Server connector: server + database -> schema.table",
        '\tSource = Sql.Database(#"SQL Server", #"SQL Database"),',
        f'\tTable = Source{{[Schema = "{SQLSERVER_SCHEMA}", Item = "{snake(name)}"]}}[Data]',
        "in",
        "\tTable",
    ]


def table_tmdl(name):
    lines = [f"/// {descriptions[name]}", f"table {q(name)}"]
    if name == "Date":
        lines.append("\tdataCategory: Time")  # marks it as the date table (with isKey on Date)
    lines.append("")
    for m in measures.get(name, []):
        lines.append(f"\t/// {m['description']}")
        dax = m["dax"].strip()
        if "\n" in dax:
            lines.append(f"\tmeasure {q(m['name'])} = ```")
            lines += [f"\t\t\t{line}" for line in dax.splitlines()]
            lines.append("\t\t\t```")
        else:
            lines.append(f"\tmeasure {q(m['name'])} = {dax}")
        if m["format"]:  # text/color helper measures have no number format
            lines.append(f"\t\tformatString: {m['format']}")
        lines += [f"\t\tdisplayFolder: {m['folder']}", ""]
    for col, dtype, opt in columns[name]:
        lines += [f"\tcolumn {q(col)}", f"\t\tdataType: {dtype}"]
        if opt.get("key"):
            lines.append("\t\tisKey")
        if opt.get("hidden"):
            lines.append("\t\tisHidden")
        if opt.get("format"):
            lines.append(f"\t\tformatString: {opt['format']}")
        if dtype != "string" or opt.get("hidden"):
            lines.append("\t\tsummarizeBy: none")
        if opt.get("category"):
            lines.append(f"\t\tdataCategory: {opt['category']}")
        if opt.get("sort_by"):
            lines.append(f"\t\tsortByColumn: {q(opt['sort_by'])}")
        # Databricks and SQL Server columns are snake_case (Delta names can't contain spaces)
        source_col = snake(col) if SOURCE in ("databricks", "sqlserver") and name in data else col
        lines += [f"\t\tsourceColumn: {source_col}", ""]
    if name == "Area":
        lines += ["\thierarchy 'Sales Hierarchy'", ""]
        for level in ["Zone", "RSM", "ASM"]:
            lines += [f"\t\tlevel {level}", f"\t\t\tcolumn: {level}", ""]
    lines += [f"\tpartition {q(name)} = m", "\t\tmode: import", "\t\tsource ="]
    if name == REFRESH_TABLE:
        # M runs only during a refresh, so this stores *when* the refresh happened
        rows = ["#table(type table [#\"Last Refreshed\" = datetime], "
                "{{DateTimeZone.RemoveZone(DateTimeZone.UtcNow())}})"]
    elif SOURCE == "databricks":
        rows = databricks_rows(name)
    elif SOURCE == "sqlserver":
        rows = sqlserver_rows(name)
    else:
        rows = embedded_rows(data[name], columns[name])
    lines += [f"\t\t\t\t{line}" for line in rows]
    return "\n".join(lines) + "\n"


(DEF_DIR / "tables").mkdir(parents=True, exist_ok=True)
for old in (DEF_DIR / "tables").glob("*.tmdl"):
    old.unlink()
for name in [*data, REFRESH_TABLE]:
    (DEF_DIR / "tables" / f"{name}.tmdl").write_text(table_tmdl(name), encoding="utf-8")
    rows = len(data[name]) if name in data else 1
    print(f"  {name:<16} {rows:>6} rows, {len(measures.get(name, []))} measures")

rel_lines = []
for fact, column, dim_name in RELATIONSHIPS:
    key = DIMENSION_KEYS[dim_name]
    rel_lines += [f"relationship '{fact} {column} to {dim_name}'",
                  f"\tfromColumn: {q(fact)}.{q(column)}",
                  f"\ttoColumn: {q(dim_name)}.{q(key)}", ""]
(DEF_DIR / "relationships.tmdl").write_text("\n".join(rel_lines), encoding="utf-8")

# Connection parameters: one place to change warehouse/catalog/schema or server/database
params = {}
if SOURCE == "databricks":
    params = {"Databricks Host": DATABRICKS_HOST, "Databricks HTTP Path": DATABRICKS_HTTP_PATH,
              "Databricks Catalog": DATABRICKS_CATALOG, "Databricks Schema": DATABRICKS_SCHEMA}
elif SOURCE == "sqlserver":
    # must match the gateway connection's server and database exactly (sqlserver_onprem_guide.md, step 6)
    params = {"SQL Server": SQLSERVER_SERVER, "SQL Database": SQLSERVER_DATABASE}

# Annotations Power BI Desktop writes itself (seen when saving the project in Desktop):
#   __PBI_TimeIntelligenceEnabled = 0  auto date/time off; we have our own Date table, so Desktop
#                                      shouldn't add hidden LocalDateTable_* tables
#   PBI_QueryOrder                     order of the Power Query queries (tables, then parameters)
query_order = json.dumps([*data, REFRESH_TABLE, *params], ensure_ascii=False, separators=(",", ":"))
(DEF_DIR / "model.tmdl").write_text("\n".join(
    ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
     "\tsourceQueryCulture: en-US", "\tdiscourageImplicitMeasures", "",
     f"annotation PBI_QueryOrder = {query_order}", "",
     "annotation __PBI_TimeIntelligenceEnabled = 0", ""]
    + [f"ref table {q(name)}" for name in [*data, REFRESH_TABLE]]) + "\n", encoding="utf-8")

expressions = DEF_DIR / "expressions.tmdl"
if params:
    # PBI_ResultType: the parameter's result type in Power Query (Desktop writes it on save)
    expressions.write_text("\n".join(
        f'expression {q(k)} = "{v}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
        f"\n\tannotation PBI_ResultType = Text\n"
        for k, v in params.items()), encoding="utf-8")
else:
    expressions.unlink(missing_ok=True)

(DEF_DIR / "database.tmdl").write_text(
    "database FMCG_Sales\n\tcompatibilityLevel: 1702\n\tcompatibilityMode: powerBI\n", encoding="utf-8")

(MODEL_DIR / "definition.pbism").write_text(json.dumps({
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "version": "4.2",
    "settings": {"qnaEnabled": True},
}, indent=2) + "\n", encoding="utf-8")

print(f"Source: {SOURCE}. Wrote {len(data) + 1} tables, {len(RELATIONSHIPS)} relationships, "
      f"{sum(len(v) for v in measures.values())} measures to {MODEL_DIR.name}/")
