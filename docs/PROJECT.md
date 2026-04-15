# OxData — Project Documentation

## Overview
Multi-project consumer survey intelligence platform.  
Each project is an independent survey dataset with its own DB, config, and dimension mappings.  
A single Streamlit chat interface switches between projects.

---

## Repository Structure

```
oxdata/
├── config/
│   ├── __init__.py
│   ├── registry.py          ← central project registry; set ACTIVE_PROJECT here
│   └── project_1.py         ← Project 1 bindings: schema, keywords, skill meta, benchmarks
│
├── data/
│   ├── project_1/
│   │   └── oxdata.db        ← star schema SQLite DB (built by ETL; auto-downloaded by db_loader)
│   ├── qualitative/
│   │   └── processed/       ← 234 interview transcript .md files
│   └── pageindex_trees/     ← pageindex retrieval trees (qualitative)
│
├── docs/
│   ├── PROJECT.md           ← this file
│   ├── SCHEMA.md            ← full DB schema + column descriptions
│   ├── LOGIC.md             ← business logic, parsing rules, known quirks
│   ├── SKILLS.md            ← Skill Foundry architecture & developer guide
│   ├── CONTEXT.md           ← how schema context is passed to the API
│   ├── BUGLOG.md            ← bug log with root causes and fixes
│   ├── PROGRESS.md          ← session-by-session progress tracker
│   └── TEST_REPORT.md       ← automated test results
│
├── etl/
│   ├── __init__.py
│   └── load_data.py         ← config-driven ETL: Excel → star schema SQLite
│
├── skills/
│   ├── __init__.py
│   ├── base_rules.py        ← Layer 1: universal SQL rules (all projects, all skills)
│   ├── foundry.py           ← assembler: route_query(), build_prompt_cache()
│   ├── thinker.py           ← complexity classifier + LLM planner + multi-query executor
│   └── capabilities/        ← Layer 2: domain logic modules (reusable across projects)
│       ├── awareness.py
│       ├── nps.py
│       ├── ownership.py
│       ├── purchase.py
│       ├── room.py
│       ├── demographic.py
│       ├── compare.py       ← comparison engine (leader/runner-up/delta detection)
│       └── insights.py      ← benchmark context builder
│
├── views/
│   ├── chat.py              ← Chat page (NL → SQL → chart → insight)
│   ├── schema.py            ← Schema Explorer (ER diagram, view/table docs)
│   ├── api_guide.py         ← API Key Guide (how to get a Groq key)
│   └── chart_renderer.py   ← chart spec parser + render_result()
│
├── app.py                   ← Streamlit entry point + st.navigation() hub
├── db_loader.py             ← downloads DB from remote source on first run (Streamlit Cloud)
├── requirements.txt
└── .env                     ← API keys (GROQ_API_KEY, GEMINI_API_KEY)
```

---

## Projects

| ID         | Name                                           | Respondents | Dates           |
|------------|------------------------------------------------|-------------|-----------------|
| project_1  | OX Wave 1 — Electrical Appliances Survey       | 6,631       | Apr–Jun 2021    |

### Adding a New Project
1. Copy `config/project_1.py` → `config/project_N.py`
2. Update: `PROJECT_ID`, `PROJECT_NAME`, `DATA_FILE`, `SHEET_NAME`
3. Update `DIMENSIONS` with the new survey's code→label mappings
4. Update `COLUMN_MAP` if the Excel uses different column names
5. Register in `config/registry.py`: add import + entry in `PROJECTS` dict
6. Run: `python etl/load_data.py --project project_N`

---

## Data Sources

### Project 1
| File | Description |
|------|-------------|
| `test data.xlsx` (sheet: `Complete Data `) | 6,631 respondents × 240 columns. Raw survey export. |
| `OX - Datamap.xlsx` (sheet: `choices`) | Code→label dimension maps used to build the DB |
| `Proj Ox_Draft Questionnaire_Master_220321.docx` | Full questionnaire instrument with question text |

**Original source location:**  
`C:\Users\tuhin\Downloads\Proj Ox_Draft Questionnaire_Master_220321 (1)\`

---

## System Flow

```
test data.xlsx
      │
      ▼
etl/load_data.py  ←── config/project_1.py (dimension maps)
      │
      ▼
data/project_1/oxdata.db  (star schema: dims + facts + views)
      │           ↑ db_loader.py auto-downloads on Streamlit Cloud
      ▼
app.py  ←── config/registry.py (which project is active)
      │
      ├── User types question in plain English
      │
      ├── skills/thinker.py — classify_complexity()
      │     ├── "simple"    → single-skill flow (below)
      │     ├── "contextual"→ single-skill flow (carry forward context)
      │     ├── "complex"   → Thinker: plan → decompose → multi-query → merge
      │     └── "summary"   → summarise prior conversation (no SQL)
      │
      ├── skills/foundry.py — route_query()  [0 API tokens — pure keyword match]
      │     └── returns skill key (nps / awareness / ownership / purchase / room / demographic / general)
      │
      ├── PROMPT_CACHE[skill_key]  [pre-assembled at startup — 0 latency]
      │     └── Layer 1 rules + skill schema slice (350–900 tokens)
      │
      ├── Groq llama-3.1-8b-instant → generates SQL
      │     └── Gemini 2.0 Flash fallback if Groq rate-limited
      │
      ├── SQL executed on oxdata.db (SQLite, read-only)
      │
      ├── skills/capabilities/compare.py — comparison engine (leader/runner-up/delta)
      ├── skills/capabilities/insights.py — benchmark context
      │
      ├── Groq llama-3.1-8b-instant → plain English summary (enriched)
      │
      └── views/chart_renderer.py — render_result() → chart + table
```

---

## Key Design Decisions

### Why star schema?
- Dimension tables hold labels; fact tables hold codes → joins are clean
- SQL queries are readable and predictable (LLM generates safer SQL)
- Scale: new projects just add new DB files; no schema changes to existing

### Why pre-built views?
- Views join facts with all dimension labels upfront
- LLM queries `v_brand_awareness WHERE brand_name = 'Crompton'` not `WHERE brand_id = 2`
- Reduces hallucination surface — no implicit code-lookup needed

### Why show SQL in the UI?
- This is a **verification system first** — user must be able to check the query
- Once patterns are validated, trust in the outputs can grow
- Prevents hallucination on numbers: SQL either returns the right count or it doesn't

### Why SQLite?
- Zero-config, file-per-project, portable
- All queries in this use-case are read-only aggregations: SQLite handles this well
- Can migrate to Postgres later by changing the connection in `registry.py`

---

## Known Limitations / TODO

- `category` column in `fact_respondents` is NULL — the `mq6` quota variable was not exported in `test data.xlsx`. Must be added manually or from a separate source.
- `sec` (NCCS socioeconomic class) was not exported. Derivable from `s4a` × `s4b` if those columns become available.
- Interview time (not just date) is available in `int_stime.1` but not loaded — can be added to `dim_date` if time-of-day analysis is needed.
- Qualitative data (234 `.md` transcripts) is stored but not yet connected to the quantitative DB.
