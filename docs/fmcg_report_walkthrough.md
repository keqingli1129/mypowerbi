# FMCG Sales Report: Walkthrough of What We Built

How the **FMCG Sales Executive Summary** was built from an Excel file, entirely from a Linux
machine (no Power BI Desktop), as a PBIP project in Git, published to **My workspace** in the
Power BI Service, and finally fed from **Databricks** with a daily scheduled refresh. Step status and commit IDs are in [roadmap.md](roadmap.md).

## The result

One page, 1920 × 1080, for sales leadership: **"Are we on target and growing?"**

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│ Are we on target and growing?                       [Year 2026▾] [Zone▾] [Category▾] │
├───────────────┬───────────────┬───────────────┬───────────────┬────────────────────┤
│ SELL-IN       │ SELL-OUT      │ % OF TARGET   │ SELL-THROUGH  │ DISTRIBUTOR STOCK  │
│ ₹124M         │ ₹139M         │ 97.2%         │ 95.3%         │ 660K               │
│ ▲ 9.4% vs LY  │ ▲ 9.3% vs LY  │ ▼ ₹3.5M below │ 4.7% still w/ │ ▲ 214,561 added    │
├───────────────┴───────────────┴──────┬────────┴───────────────┴────────────────────┤
│ Monthly sell-in vs sell-out vs target│ Gap to primary target by ASM (worst first)   │
├──────────────────────────────────────┼─────────────────────────────────────────────┤
│ Scorecard by zone ▸ ASM               │ Sell-in growth by category (2026 vs 2025)   │
├──────────────────────────────────────┴─────────────────────────────────────────────┤
│ Source: … (footer)                                                                  │
└────────────────────────────────────────────────────────────────────────────────────┘
```

The story it tells for 2026: sell-in grew 9.4% but is slightly behind target in every zone;
North grows fastest yet is furthest behind; Beverages is the only shrinking category; about 5%
of units sold to distributors don't move on to retailers, so distributor stock keeps growing.

## How the pieces fit

```
data/*.xlsx ─► tools/fmcg_data.py (shaping) ─┬─► tools/load_to_databricks.py ─► Databricks e2e_dev.fmcg (Delta)
                                              │                                        │ daily 06:00 refresh
                                              └─► tools/build_semantic_model.py         ▼
                                                    ─► FMCG_Sales.SemanticModel/ ─► Service: FMCG_Sales model
                                                       (TMDL; partitions read       ▲   ◄── tools/check_measures.py
                                                        Databricks)                 │   (report refers to measures)
tools/theme/ + tools/build_report.py ─► FMCG_Sales.Report/ (PBIR) ─► tools/publish_report.py
```

| Part | What it is |
|---|---|
| **Semantic model** | Tables, relationships and DAX measures (the formulas). Lives in the model, not the report. |
| **Report** | Pages and visuals. Each visual only **refers** to measures by name. |
| **PBIP project** | `FMCG_Sales.pbip` + `FMCG_Sales.SemanticModel/` + `FMCG_Sales.Report/`, all plain text, so Git can diff it. On Windows, double-click the `.pbip` to open it in Desktop. |

## Prerequisites

| Tool | Used for |
|---|---|
| `uv` (Python) | Running the scripts that read Excel (`pandas`, `openpyxl`) |
| Azure CLI `az`, signed in (`az login`) | API tokens for publishing and DAX queries |
| `powerbi-report-author` (`npm install -g @microsoft/powerbi-report-authoring-cli`) | Scaffolding and validating PBIR |
| Power BI account with My workspace | Where the model and report live |
| Databricks CLI, `azure` profile, `pyarrow` | Loading the tables into Databricks (Step 10) |

## Step by step

### 1–3. Understand the data, design the model, write the measures

- 8 sheets: 4 **facts** (Primary_Sales, Secondary_Sales, Targets, Coverage_Productivity),
  3 **dimensions** (Product, Distributor, Calendar), 1 KPI definition sheet.
- Sales team hierarchy: **Zone → RSM → ASM → SO → Distributor** (ASM = area sales manager).
- **Star schema with different grains**: targets exist only per **ASM × Category × Month**, so
  Area (ASM grain) and Category are separate dimensions connected directly to every fact.
  Filtering by distributor, product, sales officer or channel does **not** filter targets.
- **Date** is marked as the date table (`dataCategory: Time` + `isKey`), so
  `SAMEPERIODLASTYEAR` works.
- Measures follow the READ_ME KPIs: sales, sell-through %, achievement %, YoY/MoM, cumulative
  pipeline stock, coverage. YoY returns blank unless one year is selected, because the data only
  starts in Jan 2025.

### 4. Build the model files

```bash
uv run --no-project --with pandas --with openpyxl python -I tools/build_semantic_model.py
```

Writes TMDL to `FMCG_Sales.SemanticModel/`. Each table file has measures, columns, and a
**partition**: the M recipe that produces the rows. Here the rows are **embedded** as compressed
JSON, so the Service needs no credentials or gateway. The script stops if any fact key is missing
from its dimension.

### 4b. PBIP skeleton

`powerbi-report-author scaffold` created `FMCG_Sales.pbip` and `FMCG_Sales.Report/`, linked to the
model with `byPath` (`../FMCG_Sales.SemanticModel`).

### 5. Publish the model

```bash
python3 -I tools/publish_model.py
```

Creates (first run) or updates the model in My workspace via the Fabric API, then refreshes it.
IDs are saved to `tools/.published.env` (git-ignored).

### 6. Check the numbers

```bash
uv run --no-project --with pandas --with openpyxl python -I tools/check_measures.py
```

36 checks: DAX results from the published model vs values computed independently from the Excel
file (totals, YoY, by zone, category mix, cumulative stock, helper texts and colors).

### 7. Plan the page

One page first, sales leadership, 1920 × 1080, clean corporate look. Rules: at most 5 KPIs, each
with a comparison; color only with meaning; question as the title; detail behind a click.

### 8. Build the page (`tools/build_report.py`)

```bash
python3 -I tools/build_report.py
powerbi-report-author validate FMCG_Sales.Report
python3 -I tools/publish_report.py
```

| Sub-step | Built | Technique |
|---|---|---|
| 8a | Helper measures: context text ("▲ 9.4% vs last year") and color codes (`#1A7F37` / `#C62828`) | Measures that return text or a hex color |
| 8b | Theme, 1920×1080 grey page, title, Year/Zone/Category slicers | Custom theme registered in `report.json`; Year = strict single select, sorted newest first |
| 8c | 5 KPI tiles | Value card + context card + 4 px accent bar (`shape`) per tile |
| 8d | Monthly trend + gap by ASM | Per-series color and dash (`metadata` selector); bar color from `[Achievement Color]` |
| 8e | Scorecard matrix + growth by category | Conditional font color in a matrix (`values.fontColor`), ₹M display units (`columnFormatting`) |

Visual IDs are derived from readable keys (e.g. `exec.kpi.sellin.value`), so re-running the
script produces identical files and Git diffs show only real changes.

### 9. Final review

Checked against the design rules; colored the total row, added the source footer, filter pane
collapsed by default. Not shared (My workspace is private to its owner).

## How to make changes later

| Change | Do this |
|---|---|
| Excel data updated | Run `load_to_databricks.py`; the 06:00 refresh picks it up (or refresh now from the Service) → `check_measures.py` |
| Databricks token expired (refresh-failure email) | Generate a new token (scope: BI Tools) → Service: model **Settings → Data source credentials** |
| Work without Databricks | `build_semantic_model.py --source embedded` → `publish_model.py` |
| New or changed measure | Edit `measures` in `build_semantic_model.py` → regenerate → publish model → add a check |
| Visual, layout or theme | Edit `build_report.py` or `tools/theme/CleanCorporate.json` → `build_report.py` → validate → `publish_report.py` |
| See your change | Reopen the report (Ctrl+F5); click **Reset to default** to drop your remembered slicer choices |

## Lessons learned

- **The validator checks structure, not rendering.** A hand-written slicer default selection
  validated but made the report hang at "Loading report". It was found by bisection: an empty
  page loaded, the page without the Year slicer loaded, and adding its settings one at a time
  pointed to the default filter. Test new kinds of settings one at a time in the Service.
- **Display units are numbers** (`"1000000D"`). The text `"'1000000'"` validates but is ignored.
- **The Service remembers each viewer's slicer and filter choices.** Use **Reset to default**
  after republishing.
- **Fonts:** use font lists (`'Segoe UI', …, helvetica, arial, sans-serif`). Plain "Segoe UI"
  falls back to a serif font on Linux and Mac.
- **My workspace limits:** Power BI API paths are `/myorg/datasets/…` (no `/groups/{id}`);
  Fabric Git integration and the CLI's service preview don't work there; `.pbix` download
  returned 403 for this API-created model.
- **Model-view layout** arranged in the browser (Editing mode only; Viewing mode doesn't save)
  stays in the Service and survived model republishing, but the API doesn't export it.

### 10. Databricks as the data source

| Sub-step | What happened |
|---|---|
| 10a | Chose the `azure` profile, the Serverless Starter Warehouse and catalog/schema `e2e_dev.fmcg` |
| 10b | `load_to_databricks.py`: shaped tables → Parquet → Unity Catalog volume → `CREATE OR REPLACE TABLE … AS SELECT * FROM read_files(…)` with DATE/DECIMAL/BIGINT casts; snake_case names because Delta column names can't contain spaces; row counts verified |
| 10c | Partitions now use `Databricks.Catalogs(host, httpPath)` → catalog → schema → table; `sourceColumn` points at the snake_case columns; 4 connection parameters in `expressions.tmdl`. Measures, relationships and the report didn't change. |
| 10d | A Databricks personal access token (scope **BI Tools**) entered in the model's **Data source credentials** |
| 10e | Daily 06:00 Central refresh (`set_refresh_schedule.py`, email on failure); a `Refresh Info` table captures the refresh time for the footer ("Data refreshed … UTC"); 37 checks pass |

```bash
uv run --no-project --with pandas --with openpyxl --with pyarrow python -I tools/load_to_databricks.py
uv run --no-project --with pandas --with openpyxl python -I tools/build_semantic_model.py   # --source databricks
python3 -I tools/publish_model.py && python3 -I tools/set_refresh_schedule.py
```

