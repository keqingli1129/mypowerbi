# Building a Power BI Report with Claude: Step-by-Step Walkthrough

Source: `docs/powerbi_claudecode.txt` (video transcript)

**Goal:** have Claude build a 4-page retail Power BI report (Executive Summary, Product, Store, Customer) with page navigation. You only write prompts. Then improve the result by giving Claude business context and a wireframe, and finish with a few manual edits.

**Starting point:** a retail dataset in a star schema. It has 1 fact table and 4 dimension tables (Product, Store, Customer, Date), joined one-to-many from each dimension to the fact table. The model has **no measures** yet.

---

## Phase 0: Prerequisites

| Item | Why it's needed |
|---|---|
| Power BI Desktop (recent build with preview features) | Hosts the report and the "bridge" that lets Claude see the report |
| Claude (desktop app or Claude Code) | The agent that does the work |
| **Power BI Authoring plugin** installed in Claude | Provides the skills: report planning, report design, report authoring, semantic model authoring |
| **Power BI Modeling MCP server** configured | Lets Claude connect to the open Desktop model |
| A star-schema dataset already loaded in Desktop | Claude builds measures and visuals on top of it |

To check the plugin, go to **Claude → Customize → Plugins → Power BI Authoring**. Once it's enabled, the skills are available automatically. Type `/` in chat and search "powerbi" to list them.

---

## Phase 1: Prepare Power BI Desktop

### Step 1. Save the report as a PBIP project
1. Open your report in Power BI Desktop.
2. Go to **File → Save As**.
3. Change the file type from **.pbix** (the default) to **Power BI Project (.pbip)**.
4. Give it a name and **write the name down**, because you'll paste it into the prompt later. Click **Save** and confirm the replace if asked.
5. Check that the Desktop title bar now shows the project name.

> Why: PBIP stores the report (PBIR) and model (TMDL) as plain text files on disk. That lets Claude read, write and validate them directly.

### Step 2. Check the model
- **Table view:** confirm all 5 tables are loaded.
- **Model view:** confirm the star schema, with fact in the middle and one-to-many relationships from each dimension to the fact.
- Note that there are **no measures**. Claude will create them.

### Step 3. Turn on the bridge (external tool access)
1. Go to **File → Options and settings → Options**.
2. Open **Preview features**.
3. Turn on **"Enable external tool access to Power BI Desktop through secure local APIs."**
4. Restart Desktop if it asks you to.

> Why: the bridge lets Claude **reload the report and take screenshots of each page**. Claude then looks at its own output, spots problems and fixes them, so you don't have to describe every visual bug yourself.

---

## Phase 2: Configure Claude

### Step 4. Session settings
1. **Working folder:** set it to the folder that **contains your .pbip file**.
2. **Permission mode:** the presenter used **Bypass permissions** so Claude could run unattended.
   - ⚠️ Use this only on a throwaway or practice copy, **never on production work**. On real projects, use a mode that asks before acting.
3. **Model:** Sonnet was used. It was good enough and uses far fewer tokens than Opus. Effort was set to **High**.

### Step 5. Connect to the PBIP
Prompt:
```
Can you connect to the PBIP file?
```
Expected result: Claude reports that it found exactly one running Power BI Desktop instance, names its window title, and says it's connected.

---

## Phase 3: First Build (Prompt #1)

### Step 6. Write the build prompt
The presenter kept a structured prompt in a notebook. Before pasting it, use **find & replace** to put your actual PBIP file name in every place the prompt mentions it. (They found the name appeared twice, not once.)

The video only showed parts of the prompt, so the template below is a **reconstruction of its sections**:

```
TASK
Using the PBIP project at <path>\<YourProject>.pbip and the Power BI report
authoring skill, build a 4-page Power BI report:
  1. Executive Summary  2. Product Analysis  3. Store Analysis  4. Customer Analysis
Remove any existing pages. Create the semantic model's DAX measures if they
don't exist; modify them if they do.

ENVIRONMENT / IMPORTANT
Do NOT create the model through the modeling MCP connection.
Write the model directly as TMDL on disk.

DATA MODEL
- Dimensions: Product, Store, Customer, Date
- Fact: <fact table> (key columns, grain, facts to know)
- Optional calculated columns you may add: <list>

DESIGN
- Overall structure, theme and tone

PAGE LAYOUT
- Page 1 Executive Summary: <KPIs, charts>
- Page 2 Product: ...
- Page 3 Store: ...
- Page 4 Customer: ...

NAVIGATION
- A navigation rail with page-navigation buttons/bookmarks on every page

FILTERS & INTERACTIONS
- Which slicers to use (e.g., Year, Country, Channel), sync rules, cross-filter behavior

KNOWN PBI TRAPS
- <pitfalls to avoid>

VERIFICATION LOOP (DO NOT SKIP)
- Run PBIR validation (powerbi-report-author validate); fix every error and re-validate
- Use the Power BI modeling MCP to confirm measures evaluate
- Reload Power BI Desktop and screenshot EVERY page; fix what looks wrong

REPORT BACK
- What you built, what each verification round caught and fixed,
  judgment calls you made, and anything you deliberately left out.
```

### Step 7. Run it and let it work
- Paste the prompt and press Enter. You should see the **Power BI report authoring** skill start.
- In the video the run took **more than 10 minutes**. In that time Claude:
  1. Edited the model's TMDL files and created and updated measures.
  2. Generated the pages, ran validation, **found some errors, diagnosed them and fixed them**, and finished with **0 errors and 0 warnings**.
  3. Started the **Desktop verification loop**: it used the Power BI Modeling MCP plugin, reloaded the report, took screenshots of each page, and fixed what it saw.
  4. Wrote a final report with its judgment calls and anything it deliberately skipped.

### How the parts work together (agentic reporting workflow)
This follows the Power BI June 2026 feature update diagram:

```
You (natural-language request)
   │
   ▼
Claude (LLM)
   ├─ Report Planning  → defines the spec: pages, scope, requirements (from your prompt)
   ├─ Report Design    → layout, chart choice, KPI cards, colors, theme
   ├─ Report Authoring → writes PBIR/TMDL using the schemas, then validates
   │
   ▼
Power BI Desktop + Bridge → reload + screenshot each page
   │                         └─ screenshots go back to Claude → it fixes and repeats
   ▼
Save → Publish to Power BI Service / Fabric workspace
```

The Modeling MCP connects Claude to the live model. The **bridge** gives Claude "eyes" on the rendered pages.

---

## Phase 4: Review Output #1

### Step 8. Open the report and test it
- **Executive Summary:** many KPI cards, monthly/yearly column chart, donut chart, bar charts, a navigation bar.
- Click each nav button (Product, Store, Customer). In the video, **navigation worked** but looked poor.

### Step 9. Assess what worked and what didn't

**What worked**
- You did no manual work and got a reasonable starting point.
- **All measures were created and organized into display folders**: Core, Time Intelligence, Product, Store, Customer.
- The pages are usable for a first look at the data (e.g., total sales about $4M, gross profit about $2M, filterable by country). **You still have to check that the numbers are correct.**

**What didn't**
- **Colors have no meaning.** Blue, green and yellow are used at random. Green should mean growth and red should mean decline.
- **Wrong chart types**, e.g., a donut chart with too many categories.
- **10 KPI cards at the top of every page.** An executive wants to know whether the business grew, *why*, and which stores, categories, pricing or churn problems need attention. They don't want a wall of numbers.
- **Missing data labels** on some charts.

> Lesson: AI gives you a starting draft. The quality comes from the context and direction you provide next.

---

## Phase 5: Redesign with Business Context

### Step 10. Write down the business objectives *before* prompting again
Don't just tell Claude "create reports for me." Talk to the stakeholders (CEO, CFO, CIO, digital-transformation owner) and write down concrete objectives. Examples from the video:

1. **Store performance:** across the 10 stores, which are growing, which are declining, and how do we track and improve them?
2. **Product pricing and margin:** profit margins are low.
   - Which SKUs have **good margin and good sales**? Promote them more.
   - Which SKUs have **good margin but low sales**? Promote them too.
   - Which SKUs have **low margin but a large marketing budget**? Cut their marketing spend.

### Step 11. Redesign prompt (Prompt #2)
Structure used in the video:
```
I want you to redesign the Power BI retail analytics Executive Summary dashboard.
(The current dashboard is already open, so no screenshot is needed.)

Act as a senior Power BI dashboard designer.

LOGIC / AUDIENCE
It should help a CEO or retail manager answer:
- <business questions from Step 10>

KPI HIERARCHY
- <top-level KPIs → supporting drivers → detail>

EXAMPLES OF HOW IT SHOULD LOOK
- <reference descriptions>

Only change the Executive Summary page.
```
Add the line **"Only change the Executive Summary page"** so Claude leaves the other pages alone.

### Step 12. Add a wireframe (strongly recommended)
- Sketch the page in a wireframing tool, **or on paper**: the 3–4 KPIs, the charts, and the questions each part answers.
- Take a photo and **attach it to the Claude chat**.
- Without a wireframe, Claude gives a generic design that anyone else would also get. It will look AI-generated and people will trust it less. **You are the expert, so you set the direction.**

### Step 13. Review Claude's mockup (artifact)
Claude first listed the weaknesses of the current page (10 KPI cards, every visual given equal weight, random colors, a donut that can't be ranked at a glance). Then it produced an **HTML mockup** in an artifact panel with:
- KPI cards that show the value, **vs. last year** and **vs. target**, with growth and decline indicators
- Store and country breakdowns with YoY % and vs-target
- Green/red color by direction, with gradients used deliberately
- A cleaner navigation bar

Compare the mockup with the current page. If you like it, reply:
```
Yes, rebuild this in Power BI now.
```

### Step 14. Let it rebuild the live page
- Claude edits the PBIR files, runs validation, reloads Desktop and checks screenshots again. Expand the tool-call list to see which files and skills it used.
- This takes about 5–10 minutes.

---

## Phase 6: Review Output #2

### Step 15. Check the redesigned Executive Summary
Improvements to confirm:
- The navigation rail looks better.
- There are **5 KPI cards** instead of 10.
- There are about **5 charts**, so the page isn't crowded.
- There are **3 slicers** (e.g., Year, Country, Channel) plus a **Clear All** button.
- A **country matrix** shows This-Year Sales and YoY %.
- A **commentary/context line** updates with the filters (e.g., "FY 2017 · All countries · All channels").

Test it:
- Change Year to 2017 and confirm the visuals update.
- Pick Australia and confirm the header text reads "Australia only, all channels."
- Click a country (e.g., Canada) and confirm the other cards update.

---

## Phase 7: Manual Refinements in Desktop

### Step 16. Color YoY % with a measure (reusable)
You could set conditional formatting through each visual's rules dialog. The presenter prefers a **measure**, because one measure can be reused across many visuals.

1. In the **Time Intelligence** display folder, create:
   ```dax
   YoY CF =
   IF ( [Sales YoY %] > 0, "Green", "Red" )
   ```
   (Use hex codes like `"#1A7F37"` / `"#C62828"` for exact colors. Use your model's actual YoY measure name.)
2. Select the matrix. In the YoY % field's drop-down, choose **Conditional formatting → Font color**.
3. Set **Format style = Field value**, choose **YoY CF**, and click **OK**.
4. Result: you can see at once which countries declined (e.g., **Italy and Canada**) and which grew.

### Step 17. Add context columns
- Add **Sales PY** (previous year) and **vs Target %** to the matrix.
- Apply the same conditional-formatting measure approach to **vs Target**.

### Step 18. Set visual interactions
1. Select a visual and go to **Format → Edit interactions**.
2. On each target visual, choose **Filter** (or Highlight/None).
3. Repeat for each source visual until cross-filtering works the way users need.

> Guideline: a complex report that users can't understand is useless. Design for how they will actually use it.

---

## Phase 8: Save and Publish
1. Save the PBIP.
2. Publish to the **Power BI Service**, or connect to and publish to a **Fabric workspace**.

---

## Appendix A: Which Power BI Authoring skill does what

| Skill | Use it for |
|---|---|
| **Report planning** | Turning requirements into a page plan and spec |
| **Report design** | Tone, theme, chart choice, layout, visual appeal |
| **Report authoring** | Writing PBIR pages and visuals, validating, the Desktop screenshot loop |
| **Semantic model authoring** | Understanding the star schema, suggesting and creating relationships and measures, connecting to Fabric |
| **Power BI Modeling MCP** | Live connection between Claude and the model open in Desktop |

To confirm the MCP server is configured in the Claude desktop app, go to **Settings → Developer**.

## Appendix B: Checklist

- [ ] Report saved as **.pbip**
- [ ] Bridge preview feature **enabled**
- [ ] Claude working folder contains the .pbip
- [ ] Power BI Authoring plugin and Modeling MCP set up
- [ ] Connected to Desktop ("found exactly one running instance")
- [ ] Prompt #1 run (build all pages, verification loop, report back)
- [ ] Output #1 reviewed, **numbers checked**
- [ ] Business objectives written down with stakeholders
- [ ] Prompt #2 (redesign) + wireframe attached, scoped to one page
- [ ] Mockup approved → rebuilt in Power BI
- [ ] Conditional-formatting measures, extra columns, interactions set
- [ ] Saved and published
