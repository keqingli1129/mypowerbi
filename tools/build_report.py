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
# Font lists: Segoe UI on Windows, Power BI's web font or Helvetica/Arial elsewhere (e.g. Linux, Mac)
FONT = "'Segoe UI', wf_segoe-ui_normal, helvetica, arial, sans-serif"
FONT_SEMIBOLD = "'Segoe UI Semibold', wf_segoe-ui_semibold, helvetica, arial, sans-serif"

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


def display_units(units):
    """Display units must be a number literal ("1000000D"), not text; text is silently ignored."""
    return {"expr": {"Literal": {"Value": f"{units}D"}}}


MILLIONS = display_units(1000000)


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
            # zero padding on the visual itself, so short text boxes (footer) don't get a scrollbar
            "visualContainerObjects": {"padding": padding(0, 0, 0, 0)},
        },
    }


def text_run(text, size, weight_font=FONT, text_color=TEXT):
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


def footer_card(key, x, y, w, h, field):
    """Small right-aligned text from a measure, with no card background, sitting on the page footer."""
    default = {"selector": {"id": "default"}}
    return key, {
        "$schema": VISUAL_SCHEMA,
        "name": visual_id(key),
        "position": {"x": x, "y": y, "z": 1000, "width": w, "height": h, "tabOrder": 4000},
        "visual": {
            "visualType": "cardVisual",
            "query": {"queryState": {"Data": {"projections": [projection(field)]}}},
            "objects": {
                "label": [{**props(show=False), **default}],
                "value": [{**props(fontSize=9.0, bold=False, fontColor=color(TEXT_MUTED),
                                   horizontalAlignment="right"), **default}],
                "outline": [{**props(show=False), **default}],
            },
            "visualContainerObjects": {"background": [props(show=False)], "border": [props(show=False)],
                                       "padding": padding(0, 0, 0, 0)},
        },
    }


def no_border_container():
    """Container formatting for card pieces that together form one borderless white tile."""
    return {"border": [props(show=False)], "padding": padding(4, 4, 16, 16)}


def kpi_tile(key, x, y, w, name, value_field, context_field, accent):
    """A KPI tile = value card (label above a big value, colored accent bar) + context card below it."""
    default = {"selector": {"id": "default"}}
    value_card = {
        "$schema": VISUAL_SCHEMA,
        "name": visual_id(f"{key}.value"),
        "position": {"x": x, "y": y, "z": 2000, "width": w, "height": 96, "tabOrder": 2000},
        "visual": {
            "visualType": "cardVisual",
            "query": {"queryState": {"Data": {"projections": [projection(value_field)]}}},
            "objects": {
                "label": [{**props(show=True, text=name, position="aboveValue", fontSize=10.0,
                                   fontColor=color(TEXT_MUTED)), **default}],
                "value": [{**props(fontSize=26.0, fontColor=color(TEXT)), **default}],
                "outline": [{**props(show=False), **default}],
            },
            "visualContainerObjects": no_border_container(),
        },
    }
    context_card = {
        "$schema": VISUAL_SCHEMA,
        "name": visual_id(f"{key}.context"),
        "position": {"x": x, "y": y + 96, "z": 2000, "width": w, "height": 48, "tabOrder": 2001},
        "visual": {
            "visualType": "cardVisual",
            "query": {"queryState": {"Data": {"projections": [projection(context_field)]}}},
            "objects": {
                "label": [{**props(show=False), **default}],
                "value": [{**props(fontSize=11.0, bold=False, fontColor=color("#475569")), **default}],
                "outline": [{**props(show=False), **default}],
            },
            "visualContainerObjects": no_border_container(),
        },
    }
    # One continuous accent bar for the whole tile: a thin rectangle drawn on top of both cards
    accent_bar = {
        "$schema": VISUAL_SCHEMA,
        "name": visual_id(f"{key}.bar"),
        "position": {"x": x + 14, "y": y + 16, "z": 3000, "width": 4, "height": 112, "tabOrder": 2002},
        "visual": {
            "visualType": "shape",
            "objects": {
                "shape": [props(tileShape="rectangle")],
                "fill": [{**props(fillColor=color(accent), transparency=0.0), **default}],
                "outline": [{**props(show=False), **default}],
            },
            "visualContainerObjects": {"background": [props(show=False)], "border": [props(show=False)],
                                       "padding": padding(0, 0, 0, 0)},
        },
    }
    return [(f"{key}.value", value_card), (f"{key}.context", context_card), (f"{key}.bar", accent_bar)]


def chart_container(title, alt_text):
    """White bordered card around a chart (from the theme), with a title and alt text for screen readers."""
    return {
        "title": [props(show=True, text=title)],
        "general": [props(altText=alt_text)],
    }


def query_ref(field):
    expr = next(iter(field.values()))
    return f"{expr['Expression']['SourceRef']['Entity']}.{expr['Property']}"


def trend_chart(key, x, y, w, h, category, series):
    """Line chart with one line per measure; series = [(field, display name, color, dashed)]."""
    data_point, line_styles = [], []
    for field, _, hex_code, dashed in series:
        selector = {"selector": {"metadata": query_ref(field)}}   # applies to this measure's line only
        data_point.append({**props(fill=color(hex_code)), **selector})
        line_styles.append({**props(lineStyle="dashed" if dashed else "solid",
                                    strokeWidth=2.0 if dashed else 3.0), **selector})
    return key, {
        "$schema": VISUAL_SCHEMA,
        "name": visual_id(key),
        "position": {"x": x, "y": y, "z": 4000, "width": w, "height": h, "tabOrder": 3000},
        "visual": {
            "visualType": "lineChart",
            "query": {"queryState": {
                "Category": {"projections": [projection(category)]},
                "Y": {"projections": [projection(f, name) for f, name, _, _ in series]},
            }},
            "objects": {
                "dataPoint": data_point,
                "lineStyles": line_styles,
                "legend": [props(show=True, position="Top", fontSize=10.0)],
                "valueAxis": [props(show=True, labelDisplayUnits=MILLIONS)],
            },
            "visualContainerObjects": chart_container(
                "Monthly sell-in vs sell-out vs target",
                "Line chart of monthly primary sales, secondary sales and primary target"),
        },
    }


def ranked_bar_chart(key, x, y, w, h, category, value, value_name, color_measure, title, alt_text,
                     direction="Ascending", label_units=MILLIONS):
    """Horizontal bars sorted by value; each bar colored by a color measure (red/green)."""
    units = {"labelDisplayUnits": label_units, "labelPrecision": 1} if label_units else {}
    labels = props(show=True, **units, fontSize=10.0)
    return key, {
        "$schema": VISUAL_SCHEMA,
        "name": visual_id(key),
        "position": {"x": x, "y": y, "z": 4000, "width": w, "height": h, "tabOrder": 3100},
        "visual": {
            "visualType": "barChart",
            "query": {
                "queryState": {
                    "Category": {"projections": [projection(category)]},
                    "Y": {"projections": [projection(value, value_name)]},
                },
                "sortDefinition": {"sort": [{"field": value, "direction": direction}], "isDefaultSort": False},
            },
            "objects": {
                # color comes from the measure, evaluated per bar (conditional formatting by field value)
                "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": color_measure}}}},
                               "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
                "labels": [labels],
            },
            "visualContainerObjects": chart_container(title, alt_text),
        },
    }


def scorecard_matrix(key, x, y, w, h, rows, values, title, alt_text):
    """Matrix (pivotTable). values = [(field, display name, color measure or None, show in millions)]."""
    value_entries = []   # conditional font colors: the color measure is evaluated per cell
    column_entries = []  # static per-column formatting (display units)
    for field, _, color_measure, millions in values:
        ref = query_ref(field)
        if color_measure:
            value_entries.append({
                "properties": {"fontColor": {"solid": {"color": {"expr": color_measure}}}},
                # matchingOption 0 = data rows AND totals (so the total row is colored too)
                "selector": {"data": [{"dataViewWildcard": {"matchingOption": 0}}], "metadata": ref},
            })
        if millions:
            column_entries.append({**props(labelDisplayUnits=MILLIONS, labelPrecision=1),
                                   "selector": {"metadata": ref}})
    return key, {
        "$schema": VISUAL_SCHEMA,
        "name": visual_id(key),
        "position": {"x": x, "y": y, "z": 4000, "width": w, "height": h, "tabOrder": 3200},
        "visual": {
            "visualType": "pivotTable",
            "query": {"queryState": {
                "Rows": {"projections": [projection(f) for f in rows]},
                "Values": {"projections": [projection(f, name) for f, name, _, _ in values]},
            }},
            "objects": {
                "columnHeaders": [props(columnAdjustment="growToFit", autoSizeColumnWidth=True)],
                "values": value_entries,
                "columnFormatting": column_entries,
            },
            "visualContainerObjects": chart_container(title, alt_text),
        },
    }


# ---------------------------------------------------------------------------
# Page: Executive Summary
# ---------------------------------------------------------------------------

EXEC_PAGE = "8e4e7370b37b48acafc4"  # created by the Step 4b scaffold

exec_visuals = [
    # Header band (y 24-104): title on the left, slicers on the right
    textbox("exec.title", MARGIN, 24, 1100, 80, [
        text_run("Are we on target and growing?", 22, FONT_SEMIBOLD),
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

# KPI strip (y 128-272): 5 tiles of 352 px with 24 px gaps between the 32 px margins
BLUE, TEAL, SLATE, AMBER = "#0F6CBD", "#0E7C7B", "#475569", "#B45309"
kpis = [
    ("exec.kpi.sellin", "SELL-IN (PRIMARY)", measure("Primary Sales", "Primary Sales"),
     measure("Primary Sales", "Primary Sales Context"), BLUE),
    ("exec.kpi.sellout", "SELL-OUT (SECONDARY)", measure("Secondary Sales", "Secondary Sales"),
     measure("Secondary Sales", "Secondary Sales Context"), TEAL),
    ("exec.kpi.target", "% OF PRIMARY TARGET", measure("Targets", "Primary Achievement %"),
     measure("Targets", "Achievement Context"), SLATE),
    ("exec.kpi.sellthrough", "SELL-THROUGH", measure("Secondary Sales", "Sell-Through %"),
     measure("Secondary Sales", "Sell-Through Context"), TEAL),
    ("exec.kpi.stock", "DISTRIBUTOR STOCK (UNITS)", measure("Secondary Sales", "Pipeline Stock Units"),
     measure("Secondary Sales", "Pipeline Stock Context"), AMBER),
]
for i, (key, name, value_field, context_field, accent) in enumerate(kpis):
    exec_visuals += kpi_tile(key, MARGIN + i * (352 + 24), 128, 352, name, value_field, context_field, accent)

# Middle row (y 296-656): trend on the left (x 32-1132), gap by ASM on the right (x 1156-1888)
exec_visuals += [
    trend_chart("exec.trend", MARGIN, 296, 1100, 360, column("Date", "Month Name"), [
        (measure("Primary Sales", "Primary Sales"), "Sell-in", BLUE, False),
        (measure("Secondary Sales", "Secondary Sales"), "Sell-out", TEAL, False),
        (measure("Targets", "Primary Target"), "Primary target", "#94A3B8", True),
    ]),
    ranked_bar_chart("exec.gap_by_asm", 1156, 296, 732, 360, column("Area", "ASM"),
                     measure("Targets", "Primary Gap to Target"), "Gap to target",
                     measure("Targets", "Achievement Color"),
                     "Gap to primary target by ASM (worst first)",
                     "Bar chart of each area sales manager's gap to primary target, red when behind"),
]

# Bottom row (y 680-1016): scorecard on the left, growth by category on the right
exec_visuals += [
    scorecard_matrix("exec.scorecard", MARGIN, 680, 1100, 336, [column("Area", "Zone"), column("Area", "ASM")], [
        (measure("Primary Sales", "Primary Sales"), "Sell-in", None, True),
        (measure("Targets", "Primary Target"), "Target", None, True),
        (measure("Targets", "Primary Achievement %"), "% of target", measure("Targets", "Achievement Color"), False),
        (measure("Primary Sales", "Primary YoY %"), "YoY", measure("Primary Sales", "Primary YoY Color"), False),
        (measure("Secondary Sales", "Sell-Through %"), "Sell-through", None, False),
    ], "Scorecard by zone and ASM (click + to expand)",
        "Matrix of sell-in, target, percent of target, year-over-year growth and sell-through by zone and ASM"),
    ranked_bar_chart("exec.growth_by_category", 1156, 680, 732, 336, column("Category", "Category"),
                     measure("Primary Sales", "Primary YoY %"), "Sell-in growth",
                     measure("Primary Sales", "Primary YoY Color"),
                     "Sell-in growth by category (2026 vs 2025)",
                     "Bar chart of year-over-year sell-in growth by product category, green when growing",
                     direction="Descending", label_units=None),
    # Footer: where the numbers come from (left) and when they were last refreshed (right)
    textbox("exec.footer", MARGIN, 1028, 1400, 24, [
        text_run("Source: Databricks e2e_dev.fmcg, loaded from FMCG_Sales_Data_Suraj_Consumer.xlsx · "
                 "Data Jan 2025 – Jun 2026 · Values in Indian rupees (₹) · Sell-in = primary sales to "
                 "distributors, sell-out = secondary sales to retailers", 9, text_color=TEXT_MUTED),
    ]),
    footer_card("exec.footer.refreshed", 1456, 1024, 432, 32, measure("Refresh Info", "Last Refreshed Text")),
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
# Filter pane available but collapsed by default (Step 9 decision)
report_json["objects"] = {"outspacePane": [props(expanded=False)]}
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
