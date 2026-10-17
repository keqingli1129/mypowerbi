"""Publish FMCG_Sales.SemanticModel to My workspace, then refresh it to load the embedded data.

Creates the semantic model the first time; later runs update the same model in place.

Run from the project root:
    python3 -I tools/publish_model.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fabric  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "FMCG_Sales.SemanticModel"
NAME = "FMCG_Sales"

# 1. Find My workspace
workspace_id = fabric.my_workspace_id()
print(f"1. Workspace: My workspace ({workspace_id})")

# 2. Package the TMDL files
parts = fabric.definition_parts(MODEL_DIR, include=["definition.pbism", "definition"])
definition = {"format": "TMDL", "parts": parts}
print(f"2. Packaged {len(parts)} files from {MODEL_DIR.name}/")

# 3. Create the model, or update it if it already exists
existing = fabric.find_items(workspace_id, "SemanticModel", NAME)
if len(existing) > 1:
    sys.exit(f"{len(existing)} semantic models are named {NAME}; delete the extras first.")
if existing:
    model_id = existing[0]["id"]
    print(f"3. Updating existing semantic model {model_id}")
    status, headers, _ = fabric.call(
        "POST", f"{fabric.FABRIC}/workspaces/{workspace_id}/semanticModels/{model_id}/updateDefinition",
        {"definition": definition})
    if status == 202:
        fabric.wait_for_operation(headers, "update")
else:
    print("3. Creating semantic model")
    status, headers, body = fabric.call(
        "POST", f"{fabric.FABRIC}/workspaces/{workspace_id}/semanticModels",
        {"displayName": NAME, "description": "FMCG sales performance (embedded snapshot of the Excel workbook)",
         "definition": definition})
    if status == 202:
        body = fabric.wait_for_operation(headers, "create")
    model_id = (body or {}).get("id") or fabric.find_items(workspace_id, "SemanticModel", NAME)[0]["id"]
print(f"   Semantic model id: {model_id}")

# 4. Refresh: the Service runs each partition's M script and loads the rows
print("4. Refreshing (loading data)")
dataset = fabric.dataset_url(model_id)
fabric.call("POST", f"{dataset}/refreshes", {"notifyOption": "NoNotification"})
while True:
    time.sleep(10)
    _, _, body = fabric.call("GET", f"{dataset}/refreshes?$top=1")
    latest = body["value"][0]
    print(f"  refresh: {latest['status']}")
    if latest["status"] in ("Completed", "Failed", "Disabled", "Cancelled"):
        break
if latest["status"] != "Completed":
    sys.exit(f"Refresh failed: {latest.get('serviceExceptionJson', latest)}")

# 5. Remember the IDs for later steps (this file is in .gitignore)
(ROOT / "tools" / ".published.env").write_text(f"WORKSPACE_ID={workspace_id}\nSEMANTIC_MODEL_ID={model_id}\n")
print("5. Done. Open app.powerbi.com > My workspace > FMCG_Sales")
