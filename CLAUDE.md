# FMCG Sales Power BI project

Power BI report built as a PBIP project from code: Excel → (Databricks) → semantic model (TMDL) →
report (PBIR), published to the owner's **My workspace**. Start by reading `docs/roadmap.md` (status,
lessons learned) and `docs/fmcg_report_walkthrough.md` (how everything works).

## How the owner wants to work

- **Step by step, with explanations.** Explain what and why for one step, do only that step, show the
  result, then stop and wait for "next". Never batch several steps or build ahead autonomously.
- **Never `git commit` or `git push`.** Leave changes uncommitted, walk the owner through the diff, and
  suggest a commit message. The owner commits.
- Show uncommitted changes with `git status` / `git diff` after each step.
- Update `docs/roadmap.md` at the end of each step.

## Project facts

| Item | Value |
|---|---|
| Power BI workspace | My workspace (personal). Power BI REST paths are `/myorg/datasets/{id}`, not `/groups/{id}/…` |
| Semantic model | `FMCG_Sales`, id `07ea8c6c-fc63-4750-bdb0-0d0017bc40ad` |
| Report | `FMCG_Sales`, id `28e2cc00-ca3f-489e-9274-bedd03a43650` |
| Current data source | Azure Databricks: CLI profile `azure`, host `adb-7405618954475016.16.azuredatabricks.net`, warehouse `853d0914df399a3a`, tables in `e2e_dev.fmcg` |
| Service credentials | Databricks personal access token (scope BI Tools), created 2026-10-18 with a 13-day lifetime |
| Refresh schedule | Configured daily 06:00 Central, email on failure; currently switched **off** |
| Fallback source | `build_semantic_model.py --source embedded` (data embedded in the model, no credentials) |

`tools/.published.env` is git-ignored. On a new machine, recreate it with:

```
WORKSPACE_ID=961926b4-fab9-4ac7-962e-be4aafa23384
SEMANTIC_MODEL_ID=07ea8c6c-fc63-4750-bdb0-0d0017bc40ad
```

## Running things

All scripts run from the repo root (on Windows use `python` instead of `python3`). `-X utf8` makes
Python read/write files and print as UTF-8; Windows otherwise uses cp1252, which breaks ₹/▲/✅:

```
uv run --no-project --with pandas --with openpyxl python -I -X utf8 tools/build_semantic_model.py   # --source databricks|embedded
python3 -I -X utf8 tools/publish_model.py            # create/update model + refresh (5-15 min on shared capacity; run in background)
uv run --no-project --with pandas --with openpyxl python -I -X utf8 tools/check_measures.py         # 37 checks, must all pass
python3 -I -X utf8 tools/build_report.py
powerbi-report-author validate FMCG_Sales.Report     # after every report change
python3 -I -X utf8 tools/publish_report.py
uv run --no-project --with pandas --with openpyxl --with pyarrow python -I -X utf8 tools/load_to_databricks.py
sqlcmd -S .\SQLEXPRESS -E -C -b -i tools/sqlserver/create_tables.sql                          # once: FMCG database + tables
uv run --no-project --with pandas --with openpyxl --with pyodbc python -I -X utf8 tools/load_to_sqlserver.py
python3 -I -X utf8 tools/set_refresh_schedule.py     # turns the daily schedule on
```

Prerequisites: `uv`, Azure CLI signed in (`az login --allow-no-subscriptions`, Power BI account),
`npm install -g @microsoft/powerbi-report-authoring-cli @microsoft/powerbi-desktop-bridge-cli`
(`powerbi-report-author` and `powerbi-desktop`), Databricks CLI with profile `azure` (only for
Databricks work), the Claude Code plugins `powerbi-authoring` and `databricks`.

## Conventions and gotchas

- Shared data shaping lives in `tools/fmcg_data.py`; Databricks/SQL tables use snake_case names
  (`snake()`), the model keeps readable names and maps them through `sourceColumn`.
- Generate PBIR with `tools/build_report.py` (stable visual IDs → clean diffs); validate after every
  change. **The validator checks structure, not rendering**: test new kinds of PBIR settings one at a
  time in the Service (a hand-written slicer default selection made the report hang while loading).
- Display units must be number literals (`"1000000D"`); text values are silently ignored.
- After republishing, the owner must click **Reset to default** in the report to drop remembered
  slicer state.
- DAX variable names must not match function names (`LastDate` broke a measure).
- Never auto-select a Databricks profile; ask.

## Power BI Desktop on Windows

Done 2026-10-18: the generated PBIP opens in Desktop without errors, refreshes from Databricks and
the Executive Summary shows the same numbers as the published report.

- Desktop is the installer version (`C:\Program Files\Microsoft Power BI Desktop\`, updated by
  hand; the Microsoft Store version was removed because it had stopped updating and the bridge CLI
  can't find it without `PBI_DESKTOP_PATH`). Open the project with
  `powerbi-desktop open "<repo>\FMCG_Sales.pbip"`.
- The bridge (`powerbi-desktop status | reload | screenshot <page-id> --pid <pid> --output <png>`)
  needs Desktop **2.155 or newer**; the setting is under Options → **Security** → Desktop Bridge
  (on by default). Executive Summary page id: `8e4e7370b37b48acafc4`. Right after opening, a
  screenshot can fail ("Print metadata is not available") or catch a visual still drawing (the
  scorecard looked empty); take it again.
- Git holds no data: after opening, click **Refresh now** (Desktop asks for the Databricks personal
  access token the first time and stores it on the PC, not in Git).
- After a refresh Desktop showed "There are pending changes in your queries that haven't been
  applied" until the generator wrote `PBI_QueryOrder` (model) and `PBI_ResultType` (parameters), the
  annotations Desktop writes itself. The generator also sets `__PBI_TimeIntelligenceEnabled = 0` so
  Desktop doesn't add hidden auto date tables (`LocalDateTable_*`).
- **Don't commit what Desktop saves.** Saving rewrites ~50 files, mostly noise (random
  `lineageTag`s, schema versions, no final newline, reformatted theme/TMDL), and it turned the Year
  slicer's automatic newest-year selection into a fixed `Year = 2026` filter. Compare with
  `git diff`, carry anything useful into the generator scripts (`tools/build_semantic_model.py`,
  `tools/build_report.py`), then restore the generated files. `.pbi/` (cache, local settings) is
  git-ignored; Desktop's data cache there lets it open with data without a refresh.

## Next planned work

**On-premises SQL Server as the source**, on a Windows PC: follow `docs/sqlserver_onprem_guide.md`.
Still to write when that starts: `tools/load_to_sqlserver.py` and a `--source sqlserver` option in
`tools/build_semantic_model.py` (mirroring `--source databricks`).
