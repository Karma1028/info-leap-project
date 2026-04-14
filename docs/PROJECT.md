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
│   └── project_1.py         ← Project 1 dimension mappings + column map
│
├── data/
│   ├── project_1/
│   │   └── oxdata.db        ← star schema SQLite DB (built by ETL)
│   ├── qualitative/
│   │   └── processed/       ← 234 interview transcript .md files
│   └── pageindex_trees/     ← pageindex retrieval trees (qualitative)
│
├── docs/
│   ├── PROJECT.md           ← this file
│   ├── SCHEMA.md            ← full DB schema + column descriptions
│   ├── LOGIC.md             ← business logic, parsing rules, known quirks
│   └── PROGRESS.md          ← what is done, what is next
│
├── etl/
│   ├── __init__.py
│   └── load_data.py         ← config-driven ETL: Excel → star schema SQLite
│
├── app.py                   ← Streamlit chat interface
├── requirements.txt
└── .env                     ← API keys (GEMINI_API_KEY, GROQ_API_KEY, etc.)
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
      │
      ▼
app.py  ←── config/registry.py (which project is active)
      │
      ├── User types question in plain English
      ├── Schema context injected into Gemini prompt
      ├── Gemini generates SQL (queries the views)
      ├── SQL executed on oxdata.db
      └── Result shown as table + plain English answer
             (SQL also shown for manual verification)
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
