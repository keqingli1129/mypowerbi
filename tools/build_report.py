"""Build the FMCG_Sales report pages (PBIR files) and register the custom theme.

Each visual is written to FMCG_Sales.Report/definition/pages/<page>/visuals/<id>/visual.json.
Visual IDs are derived from a readable key, so re-running produces the same files (clean diffs).

Run from the project root, then validate:
    python3 -I tools/build_report.py
    powerbi-report-author validate FMCG_Sales.Report
"""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "FMCG_Sales.Report"
DEFINITION = REPORT / "definition"
THEME_SOURCE = ROOT / "tools" / "theme" / "CleanCorporate.json"
THEME_FILE = "CleanCorporate.json"

VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

# Design tokens (Step 7: clean corporate)
PAGE_BG = "#F1F5F9"
TEXT = "#1E293B"
TEXT_MUTED = "#64748B"
WIDTH, HEIGHT, MARGIN = 1920, 1080, 32

# ---------------------------------------------------------------------------
# Small helpers for PBIR expressions
# ---------------------------------------------------------------------------


def visual_id(key):
    """Stable 20-hex-character visual ID derived from a readable key."""
    return hashlib.md5(key.encode()).hexdigest()[:20]


def literal(value):
    """PBIR literal: strings in single quotes, booleans bare, integers with L, decimals with D."""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, int):
        text = f"{value}L"
    elif isinstance(value, float):
        text = f"{value}D"
    else:
        text = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": text}}}


def color(hex_code):
    return {"solid": {"color": literal(hex_code)}}


def column(table, name):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def measure(table, name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def projection(field, display_name=None):
    expr = next(iter(field.values()))
    table, prop = expr["Expression"]["SourceRef"]["Entity"], expr["Property"]
    proj = {"field": field, "queryRef": f"{table}.{prop}", "nativeQueryRef": prop}
    if display_name:
        proj["displayName"] = display_name
    return proj


def props(**kwargs):
    """Formatting object entry: props(show=True, fontSize=12) -> {"properties": {...}}."""
    return {"properties": {k: (v if isinstance(v, dict) else literal(v)) for k, v in kwargs.items()}}


def padding(top, bottom, left, right):
    return [props(top=float(top), bottom=float(bottom), left=float(left), right=float(right))]


# ---------------------------------------------------------------------------
# Visual builders
# ---------------------------------------------------------------------------


def textbox(key, x, y, w, h, paragraphs):
    return key, {
        "$schema": VISUAL_SCHEMA,
        "name": visual_id(key),
        "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0},
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
        },
    }


def text_run(text, size, weight_font="Segoe UI", text_color=TEXT):
    return {"textRuns": [{"value": text, "textStyle": {"fontFamily": weight_font, "fontSize": f"{size}pt",
                                                        "color": text_color}}]}


def dropdown_slicer(key, x, y, w, h, field, header, single=False, newest_first=False, sync_group=None):
    """Dropdown slicer.

    single:       strict single select (radio buttons); Power BI then always selects one item,
                  the first in the list when nothing else is selected.
    newest_first: sort the list descending, so with `single` the latest value (e.g. 2026) is the default.
                  (Used instead of a hand-written default-selection filter, which made the report hang.)
    """
    objects = {
        "data": [props(mode="Dropdown")],
        "header": [props(show=True, text=header)],
    }
    if single:
        objects["selection"] = [props(strictSingleSelect=True, selectAllCheckboxEnabled=False)]
    query = {"queryState": {"Values": {"projections": [projection(field)]}}}
    if newest_first:
        query["sortDefinition"] = {"sort": [{"field": field, "direction": "Descending"}], "isDefaultSort": False}
    visual = {
        "visualType": "slicer",
        "query": query,
        "objects": objects,
        "visualContainerObjects": {"padding": padding(8, 8, 12, 12)},
    }
    if sync_group:
        visual["syncGroup"] = {"groupName": sync_group, "fieldChanges": True, "filterChanges": True}
    return key, {
        "$schema": VISUAL_SCHEMA,
        "name": visual_id(key),
        "position": {"x": x, "y": y, "z": 1000, "width": w, "height": h, "tabOrder": 1000},
        "visual": visual,
    }


# ---------------------------------------------------------------------------
# Page: Executive Summary
# ---------------------------------------------------------------------------

EXEC_PAGE = "8e4e7370b37b48acafc4"  # created by the Step 4b scaffold

exec_visuals = [
    # Header band (y 24-104): title on the left, slicers on the right
    textbox("exec.title", MARGIN, 24, 1100, 80, [
        text_run("Are we on target and growing?", 22, "Segoe UI Semibold"),
        text_run("Sell-in, sell-out and distributor stock · data from Jan 2025 to Jun 2026", 11,
                 text_color=TEXT_MUTED),
    ]),
    # Single year only (YoY needs one year), newest first so the default is the latest year (2026)
    dropdown_slicer("exec.slicer.year", 1240, 24, 200, 80, column("Date", "Year"), "Year",
                    single=True, newest_first=True, sync_group="Year"),
    dropdown_slicer("exec.slicer.zone", 1464, 24, 200, 80, column("Area", "Zone"), "Zone",
                    sync_group="Zone"),
    dropdown_slicer("exec.slicer.category", 1688, 24, 200, 80, column("Category", "Category"), "Category",
                    sync_group="Category"),
]

# ---------------------------------------------------------------------------
# Write files
# ---------------------------------------------------------------------------


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# Theme: copy the source file and register it in report.json
resources = REPORT / "StaticResources" / "RegisteredResources"
resources.mkdir(parents=True, exist_ok=True)
shutil.copyfile(THEME_SOURCE, resources / THEME_FILE)

report_json = json.loads((DEFINITION / "report.json").read_text(encoding="utf-8"))
base = report_json["themeCollection"]["baseTheme"]
report_json["themeCollection"]["customTheme"] = {
    "name": THEME_FILE, "reportVersionAtImport": base["reportVersionAtImport"], "type": "RegisteredResources"}
report_json["resourcePackages"] = [p for p in report_json["resourcePackages"] if p["type"] != "RegisteredResources"]
report_json["resourcePackages"].append({"name": "RegisteredResources", "type": "RegisteredResources",
                                        "items": [{"name": THEME_FILE, "path": THEME_FILE, "type": "CustomTheme"}]})
write_json(DEFINITION / "report.json", report_json)

# Page: size and background; visuals folder rebuilt from scratch each run
page_dir = DEFINITION / "pages" / EXEC_PAGE
write_json(page_dir / "page.json", {
    "$schema": PAGE_SCHEMA,
    "name": EXEC_PAGE,
    "displayName": "Executive Summary",
    "displayOption": "FitToPage",
    "height": HEIGHT,
    "width": WIDTH,
    "objects": {"background": [props(color=color(PAGE_BG), transparency=0.0)]},
})
shutil.rmtree(page_dir / "visuals", ignore_errors=True)
for key, visual in exec_visuals:
    write_json(page_dir / "visuals" / visual["name"] / "visual.json", visual)
    print(f"  {key:<24} -> visuals/{visual['name']}/visual.json")
print(f"Wrote {len(exec_visuals)} visuals to the Executive Summary page")
