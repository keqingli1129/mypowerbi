"""Publish FMCG_Sales.Report to My workspace, connected to the published FMCG_Sales semantic model.

Creates the report the first time; later runs replace its definition in place (same report, same URL).
The local definition.pbir keeps its byPath link (for Power BI Desktop); only the uploaded copy is
switched to byConnection, which is what the Service requires.

Run from the project root (after tools/publish_model.py):
    python3 -I tools/publish_report.py
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fabric  # noqa: E402

SKILL = "powerbi-report-management"
ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "FMCG_Sales.Report"
NAME = "FMCG_Sales"

env = dict(line.split("=", 1) for line in (ROOT / "tools" / ".published.env").read_text().split())
workspace_id, model_id = env["WORKSPACE_ID"], env["SEMANTIC_MODEL_ID"]
print(f"1. Workspace: My workspace ({workspace_id}); semantic model {model_id}")

# 2. Package every report file (forward-slash paths); skip hidden files such as .platform
parts = fabric.definition_parts(REPORT_DIR, include=["definition.pbir", "definition", "StaticResources"])
pbir = json.loads((REPORT_DIR / "definition.pbir").read_text(encoding="utf-8"))
pbir["datasetReference"] = {"byConnection": {"connectionString": f"semanticmodelid={model_id}"}}
for part in parts:
    if part["path"] == "definition.pbir":
        part["payload"] = base64.b64encode(json.dumps(pbir, indent=2).encode("utf-8")).decode("ascii")
print(f"2. Packaged {len(parts)} files (definition.pbir switched to byConnection for the upload)")

# 3. Create the report, or replace the definition of the existing one
existing = fabric.find_items(workspace_id, "Report", NAME, skill=SKILL)
if len(existing) > 1:
    sys.exit(f"{len(existing)} reports are named {NAME}; delete the extras first.")
if existing:
    report_id = existing[0]["id"]
    print(f"3. Updating existing report {report_id}")
    status, headers, _ = fabric.call(
        "POST", f"{fabric.FABRIC}/workspaces/{workspace_id}/reports/{report_id}/updateDefinition",
        {"definition": {"parts": parts}}, skill=SKILL)
    if status == 202:
        fabric.wait_for_operation(headers, "update", skill=SKILL)
else:
    print("3. Creating report")
    status, headers, body = fabric.call(
        "POST", f"{fabric.FABRIC}/workspaces/{workspace_id}/reports",
        {"displayName": NAME, "description": "FMCG sales performance for sales leadership",
         "definition": {"parts": parts}}, skill=SKILL)
    if status == 202:  # accepted: poll, never re-POST (that would create a duplicate)
        body = fabric.wait_for_operation(headers, "create", skill=SKILL)
    report_id = (body or {}).get("id") or fabric.find_items(workspace_id, "Report", NAME, skill=SKILL)[0]["id"]

print(f"4. Done. Open: https://app.powerbi.com/groups/me/reports/{report_id}")
