# FMCG Sales Report: Roadmap

Step-by-step build of a Power BI report from `data/FMCG_Sales_Data_Suraj_Consumer.xlsx`,
authored as a PBIP project on Linux and published to **My workspace**.

Status: ✅ done · 🔄 in progress · ⬜ to do

| # | Step | Status | Commit |
|---|---|---|---|
| 0 | Git setup (`.gitignore`) | ✅ | `6742ca4` |
| 1 | Understand the data (sheets, grain, hierarchy) | ✅ | (explanation only) |
| 2 | Design the data model (star schema, different grains) | ✅ | (explanation only) |
| 3 | Write the measures (DAX) | ✅ | (explanation only) |
| 4 | Build the semantic model files (`tools/build_semantic_model.py` → TMDL) | ✅ | `acf7cc0` |
| 4b | PBIP project skeleton (`.pbip`, empty report) | ✅ | `acf7cc0` |
| 5 | Publish the model to My workspace and refresh (`tools/publish_model.py`) | ✅ | `1dd1780` |
| 6 | Check the numbers against the Excel file (`tools/check_measures.py`) | ✅ | `c7711d9` |
| 7 | Plan the report: one page first, sales leadership, 1920×1080, clean corporate | ✅ | (decisions only) |
| 8 | Build the Executive Summary page | ✅ | |
| 8a | Helper measures: KPI context text, red/green colors | ✅ | `a218897` |
| 8b | Frame: theme, page, title, Year/Zone/Category slicers | ✅ | `b9a2ac9`, `02f477f` |
| 8c | KPI strip: 5 tiles with context lines | ✅ | `4afb2e8` |
| 8d | Monthly trend chart + gap to target by ASM | ✅ | `7a6fc06` |
| 8e | Zone ▸ ASM scorecard + sell-in growth by category | ✅ | `5c6d82f` |
| 9 | Final review: total row colored, source footer, filter pane collapsed; walkthrough rewritten | ✅ | `e42ee4a` |
| 10 | Databricks as the data source | ✅ | |
| 10a | Choose workspace (azure profile), warehouse, catalog: `e2e_dev.fmcg` | ✅ | (decisions only) |
| 10b | Load the 10 tables as Delta tables (`tools/load_to_databricks.py`) | ✅ | `dc36337` |
| 10c | Model partitions read Databricks; snake_case `sourceColumn`; connection parameters | ✅ | `9c76c3c` |
| 10d | Personal access token (scope: BI Tools) entered in the Service | ✅ | (Service only) |
| 10e | Daily 06:00 Central scheduled refresh; "Data refreshed …" footer; 37 checks | ✅ | (this commit) |

## Data source today

```
Excel ──(tools/load_to_databricks.py, run manually)──► Databricks e2e_dev.fmcg ──(daily 06:00 refresh)──► Power BI
```

- Credentials: a Databricks personal access token (scope **BI Tools**, 13-day lifetime) stored in
  the semantic model's **Data source credentials**. When it expires, the 06:00 refresh fails and you
  get an email: generate a new token and paste it there.
- Fallback without Databricks: `build_semantic_model.py --source embedded` → `publish_model.py`.

## Next options

- **On-premises SQL Server as the source** (with an on-premises data gateway on a Windows machine):
  step-by-step guide in [sqlserver_onprem_guide.md](sqlserver_onprem_guide.md), not yet done.

## Lessons learned so far

- `powerbi-report-author validate` checks file structure, not rendering. A hand-written slicer
  default selection passed validation but made the report hang while loading. Test new settings
  one at a time in the Service.
- The Service remembers each viewer's slicer choices. After republishing, use **Reset to default**.
- The model-view layout made in the browser (Editing mode) stays in the Service but isn't
  exported by the API, so it isn't in Git. Republishing the model with `updateDefinition`
  did not reset it.
- Display units must be a number literal (`"1000000D"`); the text `"'1000000'"` validates but is
  silently ignored.
- Text measures returning hex colors (`Achievement Color`, `Primary YoY Color`) drive red/green on
  bars (`dataPoint.fill`) and matrix text (`values.fontColor`). Totals stay uncolored
  (`matchingOption: 1` = values only).
- My workspace uses `/myorg/datasets/...` API paths, not `/groups/{id}/...`.
- Switching the data source only changed partitions and `sourceColumn` names; all 36 existing
  checks passed unchanged against Databricks.
- The first refresh after switching to Databricks took about 13 minutes on shared capacity, although
  Databricks answered every query in under 2 seconds.
- A refresh copies Databricks → Power BI; it never re-reads the Excel file.
