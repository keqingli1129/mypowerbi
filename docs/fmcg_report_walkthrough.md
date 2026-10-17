# FMCG Sales Report: Step-by-Step Walkthrough (Linux + Power BI Service)

**Goal:** turn `data/FMCG_Sales_Data_Suraj_Consumer.xlsx` into a multi-page Power BI report for **sales leadership**, built entirely by Claude as a PBIP project on this Linux machine, then published to **My workspace** in the browser.

**How this differs from the video** (`docs/powerbi_claudecode_walkthrough.md`):

| Video setup | This setup |
|---|---|
| Power BI Desktop on Windows, report saved as .pbip | **No Desktop** (Linux). Claude writes the PBIP files directly |
| Bridge preview feature → Claude screenshots pages | **No screenshot loop.** Claude validates the files; **you** review the result in the browser |
| Data loaded from a source in Desktop | **Data embedded in the model** (a static snapshot, no gateway or credentials) |
| Publish from Desktop | Publish through the **Fabric REST API** (`az rest`) |

Status key: ✅ done · ⏳ next · 🔲 later

---

## Phase 0: Prerequisites ✅

| Item | Status |
|---|---|
| Power BI account at app.powerbi.com | ✅ (signed in, My workspace open) |
| Claude Code + **Power BI Authoring plugin** (planning, design, authoring, management skills) | ✅ |
| Azure CLI (`az`) signed in to your account, used for publishing | ✅ `az account show` works |
| Python via `uv` (to read the Excel file) | ✅ |
| Power BI Desktop | ❌ Not available on Linux. Visual checks happen in the browser instead |

---

## Phase 1: Put the data in the project ✅

### Step 1. Create the folder layout
```
mypowerbi/
├── data/FMCG_Sales_Data_Suraj_Consumer.xlsx   ← you copied this in
├── docs/                                       ← walkthroughs
├── _brief/report-spec.md                       ← (Phase 4) the approved plan
├── FMCG_Sales.pbip                             ← (Phase 5) project entry file
├── FMCG_Sales.SemanticModel/                   ← (Phase 5) TMDL model
└── FMCG_Sales.Report/                          ← (Phase 6) PBIR pages/visuals
```

### Step 2. Decide where the data lives ✅
You can't use "Save as PBIP" in the browser, and the Service **can't read a file on this laptop**. A published model is only a definition. The Service loads the data by refreshing from the source. Options considered:

| Option | Chosen? |
|---|---|
| Upload the .xlsx to OneDrive/SharePoint; the Service refreshes from it | No |
| **Embed the rows inside the model** (Power Query "Enter data" style) | ✅ **Yes** |
| Fabric Lakehouse + Direct Lake (needs a Fabric capacity workspace) | No |

**Result:** the report works right after publishing, with no credentials to set up. **Trade-off:** it's a snapshot. If the Excel file changes, ask Claude to re-embed the data and republish.

---

## Phase 2: Profile the data ✅

### Step 3. Read every sheet
Claude read the workbook with pandas. It has 8 sheets:

| Sheet | Rows | Grain | Becomes |
|---|---|---|---|
| Primary_Sales | 5,258 | 1 invoice line (company → distributor), daily | **Fact: Primary Sales** |
| Secondary_Sales | 12,637 | distributor × SKU × channel × month (dated the 15th) | **Fact: Secondary Sales** |
| Targets | 575 | ASM × Category × Month | **Fact: Targets** |
| Coverage_Productivity | 360 | SO × City × Month | **Fact: Coverage** |
| Product_Master | 18 | SKU | **Dim: Product** |
| Distributor_Master | 28 | Distributor | **Dim: Distributor** |
| Calendar | 546 | Day (1 Jan 2025 – 30 Jun 2026) | **Dim: Date** |
| READ_ME_KPIs | 12 | KPI definitions | Spec for the DAX measures |

### Step 4. Check that the data is consistent ✅
| Check | Result |
|---|---|
| Sales hierarchy is strictly nested: **Zone → RSM → ASM → SO → Distributor** | ✅ every child has exactly one parent |
| Fact rows match the master tables (ASM, Category) | ✅ |
| Every SO and city in Coverage exists in Distributor_Master | ✅ |
| Duplicate keys in Targets / Coverage | ✅ none |
| Date coverage | Jan 2025 – Jun 2026 (18 months). **YoY is only meaningful for Jan–Jun 2026 vs Jan–Jun 2025** |

Headline totals for later checks: **Primary (net) ≈ ₹358.7M**, **Secondary ≈ ₹404.3M**.

---

## Phase 3: Gather requirements (planning skill) ⏳

The `powerbi-report-planning` skill asks one question at a time, then locks a spec.

| Round | Question | Answer |
|---|---|---|
| 0 | Data source / delivery | ✅ Embedded data → My workspace |
| 1 | Audience | ✅ **Sales leadership** (national/zonal heads) |
| 3 | Report shape (pages) | ⏳ **Your approval needed.** Draft below |
| 4 | Look and feel (tone + signature visual) | 🔲 |

### Step 5. Draft page plan (to approve or change)
Follows the "Executive + Drill" pattern: start on a KPI landing page, then drill into the causes.

| # | Page | Answers | Main visuals |
|---|---|---|---|
| 1 | **Executive Summary** | Are we on target for sell-in and sell-out? Growing vs last year? | 4–5 KPI cards with vs-target and YoY; Primary vs Secondary vs Target monthly trend; achievement by Zone |
| 2 | **Zone & Team Performance** | Which zones/ASMs are behind target, and by how much? | ASM ranking bar (achievement %), Zone → RSM → ASM matrix with red/green formatting |
| 3 | **Product & Channel** | Which categories/brands/SKUs and channels drive growth? Where is scheme spend high but sales low? | Category/brand mix bars, channel split, SKU scatter (sales vs scheme spend %) |
| 4 | **Distributor Health & Coverage** | Is stock piling up at distributors? Are salesmen covering outlets? | Pipeline stock trend, distributor table (sell-through %), numeric distribution %, productive call %, lines per bill by SO |

Global slicers: **Financial Year / Month, Zone, Category** (Channel only on page 3).

---

## Phase 4: Lock the spec 🔲

### Step 6. Claude writes `_brief/report-spec.md`
- A readable summary (audience, pages, measures, design) for you to approve
- A **Design Brief YAML** block from the design skill. It gives exact page size (1920×1080), grid regions, visual placements and color rules, and is the contract the authoring step builds from

### Step 7. You approve it
Nothing gets built until you reply "Approve". You can also ask for changes to the audience, pages or design first.

---

## Phase 5: Build the semantic model (TMDL on disk) 🔲

### Step 8. Model design (star schema with a sales-team chain)
```
              Category ──────────────┐
                 │                   ▼
                 ▼                Targets ◄── ASM (Zone, RSM)
Date ──►  Product ──► Primary Sales ◄── Distributor ◄── SO ◄── ASM
  │            └────► Secondary Sales ◄──┘                │
  └──► (all 4 facts)                    Coverage ◄────────┘
```
- All relationships are one-to-many and filter from the dimension to the fact, single direction.
- Facts keep only keys and numbers. Names, zones and categories live in the dimension tables. This keeps the embedded data small and makes slicers filter every fact consistently.
- Targets/Coverage use a **month-start date** to join to Date. Secondary rows (dated the 15th) join directly.
- **Limit:** a City slicer filters sales but **not** Targets (those are set at ASM level). This is called out in the spec.

### Step 9. Embed the data
Each table's Power Query (M) partition holds its rows as compressed, base64-encoded JSON (the same mechanism as Desktop's "Enter data"). There's no external data source.

### Step 10. Measures (from the READ_ME_KPIs sheet)
Grouped into display folders:

```dax
-- Core
Primary Sales      = SUM ( 'Primary Sales'[Net_Primary_Value] )
Secondary Sales    = SUM ( 'Secondary Sales'[Secondary_Value] )
Primary Units      = SUM ( 'Primary Sales'[Units] )
Secondary Units    = SUM ( 'Secondary Sales'[Units_Sold] )
Sell-Through %     = DIVIDE ( [Secondary Units], [Primary Units] )

-- Targets
Primary Target         = SUM ( Targets[Primary_Target] )
Secondary Target       = SUM ( Targets[Secondary_Target] )
Primary Achievement %  = DIVIDE ( [Primary Sales], [Primary Target] )
Secondary Achievement %= DIVIDE ( [Secondary Sales], [Secondary Target] )

-- Time intelligence
Primary Sales PY = CALCULATE ( [Primary Sales], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )
Primary YoY %    = DIVIDE ( [Primary Sales] - [Primary Sales PY], [Primary Sales PY] )
Primary Sales PM = CALCULATE ( [Primary Sales], DATEADD ( 'Date'[Date], -1, MONTH ) )
Primary MoM %    = DIVIDE ( [Primary Sales] - [Primary Sales PM], [Primary Sales PM] )
-- (same pattern for Secondary)

-- Distributor pipeline
Pipeline Stock Units =
    CALCULATE ( [Primary Units] - [Secondary Units],
                FILTER ( ALL ( 'Date' ), 'Date'[Date] <= MAX ( 'Date'[Date] ) ) )

-- Coverage & productivity
Numeric Distribution % = DIVIDE ( SUM ( Coverage[Outlets_Billed] ), SUM ( Coverage[Total_Outlets] ) )
Productive Call %      = DIVIDE ( SUM ( Coverage[Productive_Calls] ), SUM ( Coverage[Planned_Calls] ) )
Avg Lines per Bill     = DIVIDE ( SUMX ( Coverage, Coverage[Avg_Lines_Per_Bill] * Coverage[Outlets_Billed] ),
                                  SUM ( Coverage[Outlets_Billed] ) )   -- weighted, not a plain average

-- Trade spend & mix
Scheme Spend %   = DIVIDE ( SUM ( 'Primary Sales'[Scheme_Discount] ), SUM ( 'Primary Sales'[Gross_Value] ) )
Category Mix %   = DIVIDE ( [Secondary Sales], CALCULATE ( [Secondary Sales], ALL ( Category ), ALL ( Product ) ) )

-- Formatting helpers (the video's "measure once, reuse everywhere" trick)
Achievement Color = IF ( [Primary Achievement %] >= 1, "#1A7F37", "#C62828" )
YoY Color         = IF ( [Primary YoY %] >= 0,        "#1A7F37", "#C62828" )
```

### Step 11. Check the measures against pandas
With no Desktop to run DAX in, Claude checks the numbers in pandas: totals by month, zone and category for Primary, Secondary, Target and Sell-Through %. You can compare the same figures with the report in Phase 8.

---

## Phase 6: Build the report (PBIR) 🔲

### Step 12. Create the pages from the Design Brief
Using the `powerbi-report-authoring` skill:
- Page size 1920×1080. Title on the left of the header band, slicers top-right, visuals below, with no overlaps.
- Custom theme based on the plugin's base theme. **Green means on target or growing, red means behind.** Colors are never decorative.
- Readable names on every axis, legend and column (no `Sum of Net_Primary_Value`), percentages formatted as %, and alt text on every chart.
- A navigation bar on every page.

### Step 13. Validate the files
- Validate the PBIR against its schemas, fix any errors, and run validation again until there are 0 errors.
- Check that all JSON parses and that `definition.pbir` points to the semantic model.
- Count pages and visuals against the spec.

> In the video, Desktop screenshots caught layout bugs here. On Linux that step moves to **Phase 8 (you, in the browser)**.

---

## Phase 7: Publish to My workspace 🔲

Claude does this with the `powerbi-report-management` skill and `az rest`:

### Step 14. Find the workspace
`GET https://api.fabric.microsoft.com/v1/workspaces` → pick the one with `type: Personal` (My workspace).

### Step 15. Create the semantic model
`POST /v1/workspaces/{id}/semanticModels` with every TMDL file as a base64 definition part. Poll the long-running operation until it reports `Succeeded`.

### Step 16. Load the data (refresh)
Trigger one refresh through the Power BI REST API. Because the data is embedded, **no credentials or gateway are needed**. Wait for it to finish with status `Completed`.

### Step 17. Create the report
`POST /v1/workspaces/{id}/reports` with all PBIR parts. Its `definition.pbir` points to the new semantic model **by ID** (`byConnection`).

> **Risk:** some tenants limit creating items through the API in **My workspace**. If that happens, the fallback is to create a regular workspace (needs a Pro or Fabric license) and publish there. Claude will ask you before doing that.

---

## Phase 8: Review in the browser (you) 🔲

### Step 18. Open it
1. Go to app.powerbi.com → **My workspace**.
2. You should see **FMCG_Sales** (semantic model) and **FMCG_Sales** (report).
3. Open the semantic model and check **Refresh history**. The single refresh should show **Completed**.

### Step 19. Check the numbers
| Check | Expected |
|---|---|
| Primary Sales, all periods | ≈ ₹358.7M |
| Secondary Sales, all periods | ≈ ₹404.3M |
| Primary Sales Jan 2025 | ≈ ₹16.2M |
| Primary YoY % with FY/Year = 2026 | Compares Jan–Jun 2026 with Jan–Jun 2025 only |

### Step 20. Check the layout and interactions
- Click through every page with the nav buttons.
- Change each slicer and confirm the cards and charts update.
- Click a bar (e.g., a Zone) and confirm the other visuals cross-filter.
- Look for clipped text, overlapping visuals, unreadable labels and wrong colors.

### Step 21. Send feedback
Tell Claude what to change, or take a screenshot and attach it. Claude edits the local PBIP and republishes (an update, not a new copy). You can also edit directly in the browser (**Edit** on the report). If you do, tell Claude so it can download the latest definition before making further changes.

---

## Phase 9: Later 🔲
- **Refreshable data:** move the .xlsx to OneDrive/SharePoint and switch the partitions to read from it.
- **Desktop round-trip:** copy the PBIP folder to a Windows PC and open `FMCG_Sales.pbip` in Desktop to unlock the screenshot loop from the video.
- **Share:** move to a shared workspace (My workspace is private to you).

---

## Checklist
- [x] Excel file in `data/`
- [x] Data location chosen (embedded)
- [x] Data profiled, hierarchy and grain checked
- [x] Audience: sales leadership
- [ ] Page plan approved
- [ ] Look and feel chosen
- [ ] `_brief/report-spec.md` approved
- [ ] TMDL model + measures written, numbers checked in pandas
- [ ] PBIR report written, 0 validation errors
- [ ] Published: semantic model ✓, refresh Completed ✓, report ✓
- [ ] Reviewed in browser, feedback applied
