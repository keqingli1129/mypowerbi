# Guide: On-Premises SQL Server as the Data Source

How to switch the **FMCG_Sales** semantic model from Databricks to an **on-premises SQL Server**,
refreshed in the Power BI Service through an **on-premises data gateway**. Written to be followed
later on a **Windows PC** that can reach a SQL Server. Nothing here has been run yet.

For how the project works today, see [fmcg_report_walkthrough.md](fmcg_report_walkthrough.md);
for status, see [roadmap.md](roadmap.md).

## What changes (and what doesn't)

```
 Power BI Service (cloud)                          Your network
 ┌─────────────────────┐   outbound only    ┌───────────────────────────┐
 │ FMCG_Sales model    │◄═══ Azure Relay ═══│ Gateway (Windows machine) │──► SQL Server
 │ (scheduled refresh) │                    │ runs the refresh queries  │    database FMCG
 └─────────────────────┘                    └───────────────────────────┘    schema fmcg
```

| Changes | Doesn't change |
|---|---|
| Each table's **partition** (M code) | All measures, relationships, column names, formats |
| **`sourceColumn`** names (snake_case, as for Databricks) | The report |
| **Parameters** (server and database instead of Databricks host and path) | `tools/check_measures.py` (all checks must still pass) |
| **New:** a gateway, a gateway connection, and binding the model to it | |

The on-premises data gateway is needed because the Service (in the cloud) can't reach a server
inside your network. It is **Windows-only** software that makes outbound connections only, so no
inbound firewall ports are needed.

## Before you start: checklist

| Item | Notes |
|---|---|
| Windows PC or server for the **gateway** | Windows 10/11 or Windows Server 2019+, .NET Framework 4.8, **always on** (not a laptop that sleeps), wired network preferred. You must be a local admin to install. |
| **SQL Server** reachable from that machine | Note the exact server name, e.g. `sql01.district.local` or `sql01\SQLEXPRESS`. The gateway machine must reach it on port 1433 (or the instance's port). |
| A database you can create tables in | This guide uses database `FMCG`, schema `fmcg` |
| A SQL account for Power BI | Read-only, see step 1 |
| This repo cloned on the Windows PC | `git clone https://github.com/keqingli1129/mypowerbi.git` |
| Tools on the Windows PC | `uv` (Python), Azure CLI (`az login`), Microsoft **ODBC Driver 18 for SQL Server**, optionally SSMS |
| Power BI account | The same one that owns My workspace |
| Optional: Power BI Desktop | Lets you open `FMCG_Sales.pbip` and check the data in Power Query before publishing |

Run Python commands on Windows the same way as here, e.g.
`uv run --no-project --with pandas --with openpyxl python -I tools/check_measures.py`.

## Step 1: Database, schema and read-only login

In SSMS (or `sqlcmd`), as an admin:

```sql
CREATE DATABASE FMCG;
GO
USE FMCG;
GO
CREATE SCHEMA fmcg;
GO

-- Read-only account for the Power BI gateway (SQL authentication).
-- With Windows authentication, create a login for a domain service account instead.
CREATE LOGIN powerbi_reader WITH PASSWORD = '<strong password>';
CREATE USER powerbi_reader FOR LOGIN powerbi_reader;
GRANT SELECT ON SCHEMA::fmcg TO powerbi_reader;
GO
```

**Why:** least privilege. Power BI only ever reads, and only the `fmcg` schema.

## Step 2: Create the 10 tables

Same names and types as the Databricks tables (snake_case, because that's what the model's
`sourceColumn` lines will point to). Text columns are `NVARCHAR(100)` for simplicity.

```sql
USE FMCG;
GO
CREATE TABLE fmcg.[date] (
    [date] DATE NOT NULL PRIMARY KEY,
    [year] BIGINT NOT NULL,
    month_number BIGINT NOT NULL,
    year_month_number BIGINT NOT NULL,
    month_name NVARCHAR(100) NOT NULL,
    [month] NVARCHAR(100) NOT NULL,
    [quarter] NVARCHAR(100) NOT NULL,
    financial_year NVARCHAR(100) NOT NULL
);
CREATE TABLE fmcg.area (
    zone NVARCHAR(100) NOT NULL,
    rsm NVARCHAR(100) NOT NULL,
    asm NVARCHAR(100) NOT NULL PRIMARY KEY
);
CREATE TABLE fmcg.sales_officer (
    sales_officer NVARCHAR(100) NOT NULL PRIMARY KEY,
    asm NVARCHAR(100) NOT NULL
);
CREATE TABLE fmcg.distributor (
    distributor_code NVARCHAR(100) NOT NULL PRIMARY KEY,
    distributor NVARCHAR(100) NOT NULL,
    [state] NVARCHAR(100) NOT NULL,
    city NVARCHAR(100) NOT NULL
);
CREATE TABLE fmcg.category (
    category NVARCHAR(100) NOT NULL PRIMARY KEY
);
CREATE TABLE fmcg.product (
    sku_code NVARCHAR(100) NOT NULL PRIMARY KEY,
    brand NVARCHAR(100) NOT NULL,
    sku NVARCHAR(100) NOT NULL,
    pack NVARCHAR(100) NOT NULL,
    mrp DECIMAL(18, 2) NOT NULL,
    units_per_case BIGINT NOT NULL,
    ptr DECIMAL(18, 2) NOT NULL,
    pts DECIMAL(18, 2) NOT NULL
);
CREATE TABLE fmcg.primary_sales (
    [date] DATE NOT NULL,
    asm NVARCHAR(100) NOT NULL,
    sales_officer NVARCHAR(100) NOT NULL,
    category NVARCHAR(100) NOT NULL,
    distributor_code NVARCHAR(100) NOT NULL,
    sku_code NVARCHAR(100) NOT NULL,
    units BIGINT NOT NULL,
    gross_value BIGINT NOT NULL,
    scheme_discount DECIMAL(18, 2) NOT NULL,
    net_primary_value DECIMAL(18, 2) NOT NULL
);
CREATE TABLE fmcg.secondary_sales (
    [date] DATE NOT NULL,
    asm NVARCHAR(100) NOT NULL,
    sales_officer NVARCHAR(100) NOT NULL,
    category NVARCHAR(100) NOT NULL,
    distributor_code NVARCHAR(100) NOT NULL,
    sku_code NVARCHAR(100) NOT NULL,
    channel NVARCHAR(100) NOT NULL,
    units_sold BIGINT NOT NULL,
    secondary_value DECIMAL(18, 2) NOT NULL
);
CREATE TABLE fmcg.targets (
    [date] DATE NOT NULL,
    asm NVARCHAR(100) NOT NULL,
    category NVARCHAR(100) NOT NULL,
    primary_target_value BIGINT NOT NULL,
    secondary_target_value BIGINT NOT NULL
);
CREATE TABLE fmcg.coverage (
    [date] DATE NOT NULL,
    asm NVARCHAR(100) NOT NULL,
    sales_officer NVARCHAR(100) NOT NULL,
    total_outlets BIGINT NOT NULL,
    outlets_billed BIGINT NOT NULL,
    planned_calls BIGINT NOT NULL,
    productive_calls BIGINT NOT NULL,
    lines_per_bill DECIMAL(18, 2) NOT NULL
);
GO
```

Words like `date`, `year`, `month` and `state` are bracketed because they're also SQL keywords.

## Step 3: Load the data

The shaping code is already shared in `tools/fmcg_data.py`, so the SQL Server tables will match the
model exactly. Two options:

**Option A (recommended): a loader script, like `load_to_databricks.py`.** Ask Claude on the
Windows PC to write `tools/load_to_sqlserver.py`. It would read `load_tables()`, rename columns with
`snake()`, `TRUNCATE` each table and insert the rows with `pyodbc` (`fast_executemany=True`), then
compare row counts. Expected counts:

| Table | Rows | Table | Rows |
|---|---|---|---|
| date | 546 | product | 18 |
| area | 8 | primary_sales | 5,258 |
| sales_officer | 17 | secondary_sales | 12,637 |
| distributor | 28 | targets | 575 |
| category | 4 | coverage | 360 |

**Option B: by hand.** SSMS → right-click database `FMCG` → **Tasks → Import Flat File**, one CSV per
table (exported from `load_tables()` with snake_case headers), mapping into the tables from step 2.

Quick check afterwards:

```sql
SELECT SUM(net_primary_value) FROM fmcg.primary_sales;    -- expect 358668948.53
SELECT SUM(secondary_value)   FROM fmcg.secondary_sales;  -- expect 404338998.40
```

## Step 4: Point the model at SQL Server

Add a third source to `tools/build_semantic_model.py`: `--source sqlserver` (ask Claude to add it;
it mirrors `--source databricks`).

**Parameters** (`definition/expressions.tmdl`):

```
expression 'SQL Server' = "sql01.district.local" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]

expression 'SQL Database' = "FMCG" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]
```

**Partition** for each table (here `Targets`):

```
	partition Targets = m
		mode: import
		source =
				let
					// SQL Server connector: server -> database -> schema.table
					Source = Sql.Database(#"SQL Server", #"SQL Database"),
					Table = Source{[Schema = "fmcg", Item = "targets"]}[Data]
				in
					Table
```

All 10 tables use this same pattern; only `Item` changes. The file is
`FMCG_Sales.SemanticModel/definition/tables/<Model table>.tmdl`, and the partition is the block at the
bottom of each file:

| Model table (file) | Partition name | `Item =` (SQL table `fmcg.<item>`) |
|---|---|---|
| `Date.tmdl` | `Date` | `"date"` |
| `Area.tmdl` | `Area` | `"area"` |
| `Sales Officer.tmdl` | `'Sales Officer'` | `"sales_officer"` |
| `Distributor.tmdl` | `Distributor` | `"distributor"` |
| `Category.tmdl` | `Category` | `"category"` |
| `Product.tmdl` | `Product` | `"product"` |
| `Primary Sales.tmdl` | `'Primary Sales'` | `"primary_sales"` |
| `Secondary Sales.tmdl` | `'Secondary Sales'` | `"secondary_sales"` |
| `Targets.tmdl` | `Targets` | `"targets"` |
| `Coverage.tmdl` | `Coverage` | `"coverage"` |
| `Refresh Info.tmdl` | `'Refresh Info'` | **no change**: keeps its `#table(…DateTimeZone.UtcNow()…)` recipe, which reads no source |

For comparison, the Databricks partition being replaced (4 steps: connect → catalog → schema →
table) versus the SQL Server one (2 steps: connect to server and database → schema.table):

```
// Databricks (today)
Source  = Databricks.Catalogs(#"Databricks Host", #"Databricks HTTP Path", [Catalog = null, Database = null]),
Catalog = Source{[Name = #"Databricks Catalog", Kind = "Database"]}[Data],
Schema  = Catalog{[Name = #"Databricks Schema", Kind = "Schema"]}[Data],
Table   = Schema{[Name = "targets", Kind = "Table"]}[Data]

// SQL Server (after step 4)
Source  = Sql.Database(#"SQL Server", #"SQL Database"),
Table   = Source{[Schema = "fmcg", Item = "targets"]}[Data]
```

If you edit by hand in **Power BI Desktop** instead of using the build script: **Transform data** →
select a query → **Advanced Editor** → replace the `let … in` text with the SQL Server version →
repeat for each table → **Close & Apply** → **File → Save** (the PBIP files update).

**`sourceColumn`** stays snake_case (`primary_target_value`, …), exactly as for Databricks. The
`Refresh Info` table is unchanged (it doesn't read any source).

About M steps and **query folding**: `Sql.Database` turns simple steps (navigate, filter, choose
columns, rename) into one SQL query that runs on the server. Our partitions only navigate to a
ready-made table, so there's nothing that can break folding. If you ever add logic, prefer a SQL
**view** and point the partition at it.

Optional check in **Power BI Desktop**: open `FMCG_Sales.pbip` → **Transform data** → confirm each
query shows rows → **Close & Apply** → the visuals should show the same numbers as the published
report.

## Step 5: Install the gateway

On the always-on Windows machine (local admin):

1. Download the **on-premises data gateway (standard mode)**:
   <https://go.microsoft.com/fwlink/?LinkId=2116849&clcid=0x409>
2. Install with the default path → sign in with the **work account you use for Power BI**.
3. **Register a new gateway on this computer** → name it (e.g. `FMCG-GW`) → set a **recovery key**
   and store it somewhere safe (Microsoft can't recover it; you need it to move or restore the
   gateway).
4. The installer shows the gateway as **online**.

Personal mode also exists (one user, Power BI only), but standard mode is the recommended choice.

## Step 6: Create the gateway connection

app.powerbi.com → gear icon → **Manage connections and gateways** → **Connections** → **New**:

| Field | Value |
|---|---|
| Type | **On-premises** |
| Gateway cluster | `FMCG-GW` |
| Connection name | `FMCG SQL Server` |
| Connection type | **SQL Server** |
| Server | **exactly** the `SQL Server` parameter value (`sql01.district.local` ≠ `sql01`) |
| Database | **exactly** `FMCG` |
| Authentication | **Basic** (`powerbi_reader` + password), or **Windows** with a domain account |
| Privacy level | **Organizational** |

The names must match the M code character for character, or the model can't be mapped to the
connection in step 7.

## Step 7: Publish and bind the model to the gateway

1. Publish the model: `python -I tools/publish_model.py`. Its refresh fails until the model is bound,
   just as it failed before the Databricks token was entered.
2. Service → **FMCG_Sales** (semantic model) → **Settings** → **Gateway and cloud connections** →
   enable **Use an On-premises or VNet data gateway** → for the SQL Server data source, choose
   `FMCG SQL Server` in **Maps to** → **Apply**.
   (Programmatic alternative: the Power BI `BindToGateway` REST API, or the Fabric
   `bindConnection` API.)
3. The old Databricks credentials can stay; they're simply no longer used.

## Step 8: Refresh, schedule, check

1. Refresh now (model page → **Refresh now**), or ask Claude to trigger it.
2. Turn the schedule on: **Settings → Refresh** → toggle **On** → **Apply**, or
   `python -I tools/set_refresh_schedule.py`. The gateway machine must be **on** at refresh time.
3. Run the checks:
   ```
   uv run --no-project --with pandas --with openpyxl python -I tools/check_measures.py
   ```
   All 37 must pass. The numbers are the same data, only from a different source.
4. Open the report: the footer shows the new "Data refreshed … UTC" time. Update the footer's source
   text in `tools/build_report.py` to name SQL Server, then `build_report.py` → validate →
   `publish_report.py`.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Refresh fails, "data source not mapped" / can't pick the connection in step 7 | Server or database name in the gateway connection differs from the M parameters; make them identical |
| Gateway shows **offline** | The gateway machine is off, asleep or lost internet; the gateway service isn't running |
| Login failed for user | Wrong password, or the login lacks `SELECT` on schema `fmcg` |
| Can't reach the server from the gateway | Firewall or port (1433), wrong instance name, SQL Server not allowing TCP/IP |
| Windows authentication fails | The gateway machine must be domain-joined with a trust to the SQL Server's domain |
| Slow refresh | Check query folding (keep steps simple, use views); gateway machine resources; wired network |
| Certificate or encryption errors | Newer drivers encrypt by default; install a trusted certificate on SQL Server, or (test only) allow trusting the server certificate |

## Going further

- **High availability:** add a second machine to the gateway **cluster**.
- **Keep the gateway updated** (a new version is released monthly).
- **DirectQuery** instead of Import: every visual queries SQL Server live through the gateway; size
  the gateway machine for report traffic.
- **Service account:** use a dedicated domain account or SQL login owned by IT, not a personal one.
