# Skill Foundry — Architecture & Developer Guide

## What it is

The Skill Foundry is a zero-token routing and prompt assembly system. It ensures that every
question asked in the chat only sends the LLM the schema slice it actually needs, instead of
dumping the full database schema every time.

**Key guarantee:** No API calls happen in this system. All routing is pure keyword matching.
All prompt assembly is pure Python string formatting. Everything runs at startup or on the
first question — never mid-conversation without the user's input.

---

## The Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — Universal Rules                skills/base_rules.py      │
│  "SQL only. Views only. Count+pct. Penetration formula."             │
│  Identical for ALL projects and ALL skills.                          │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 2 — Domain Capability Logic        skills/capabilities/*.py   │
│  "How does NPS work? What is a brand funnel?"                        │
│  Reusable across projects. Only changes if the business concept      │
│  itself changes (e.g., NPS definition changes).                      │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 3 — Project Schema Bindings        config/project_N.py        │
│  "My NPS view is called v_brand_nps. My score column is nps_score."  │
│  The ONLY thing that changes per project. A plain Python dict.       │
└─────────────────────────────────────────────────────────────────────┘
```

The foundry (`skills/foundry.py`) is the assembler. It reads all three layers and combines
them into a complete system prompt. The final prompt = Layer 1 + Layer 2(Layer 3).

---

## Layer 1 — Universal Rules (`skills/base_rules.py`)

Contains SQL rules that apply to every question in every project:

1. Return only raw SQL (no markdown fences, no comments)
2. Query views only — never raw `fact_*` tables
3. Penetration formula: `ROUND(COUNT(DISTINCT respondent_id) * 100.0 / (SELECT COUNT(*) FROM {respondent_table}), 1)`
4. Always include both `count` and `pct` columns in results
5. Carry forward filters from prior SQL on follow-up questions
6. Never invent column names that weren't described

**One parameter:** `respondent_table` — the base table for denominator calculations.
Set in `config/project_N.py` as `RESPONDENT_TABLE`.

```python
from skills import base_rules
rules = base_rules.get_rules("fact_respondents")  # → full rules string
```

---

## Layer 2 — Capability Modules (`skills/capabilities/*.py`)

Each capability module defines the business logic and SQL patterns for one domain.
The module is project-agnostic — it uses placeholder keys that get filled in from
the project config at runtime.

### Required interface

Every capability module must define:

| Name | Type | Purpose |
|---|---|---|
| `CAPABILITY_ID` | `str` | Unique identifier — must match the key in `REGISTRY` and `CAPABILITIES` dict |
| `DESCRIPTION` | `str` | One-line description (used in error messages) |
| `KEY_COLUMNS_SUMMARY` | `str` | Template string used in GENERAL skill's compact overview |
| `format_prompt(binding, shared_cols, respondent_table)` | `function → str` | Assembles Layer 2+3 portion of the system prompt |

### `format_prompt` contract

```python
def format_prompt(binding: dict, shared_cols: str, respondent_table: str) -> str:
    """
    Args:
        binding:          Dict of project-specific values (view name, column names, etc.)
                          Comes from config/project_N.CAPABILITIES["this_capability_id"]
        shared_cols:      String describing demographic/geo columns shared across all views.
                          Comes from config/project_N.SHARED_VIEW_COLS
        respondent_table: Name of the respondent fact table for denominator calculations.
                          Comes from config/project_N.RESPONDENT_TABLE

    Returns:
        String to append to the Layer 1 rules. Should contain:
        - VIEW section (view name, row count, key columns)
        - Business rules specific to this domain
        - 2-3 example SQL queries
    """
```

### Registered capabilities

| CAPABILITY_ID | File | Domain | Key binding keys |
|---|---|---|---|
| `awareness` | `awareness.py` | Brand awareness funnel (TOM/SPONT/AIDED) | view, entity_col, stage_col, tom_value, spont_value, aided_value |
| `nps` | `nps.py` | Net Promoter Score (0-10 scale) | view, score_col, category_col, promoter_min, detractor_max, min_raters |
| `ownership` | `ownership.py` | Binary ownership/penetration (tick-box) | view, entity_col, entity_list |
| `purchase` | `purchase.py` | Ranked purchase behaviour | view, entity_col, rank_col, max_rank, rank_desc |
| `room` | `room.py` | Room/home appliance ownership | view, entity_col, entity_list |
| `demographic` | `demographic.py` | Respondent profiles, geo, time | view, id_col, name_col, gender_col, age_col, city_col, zone_col, date_col |

---

## Layer 3 — Project Bindings (`config/project_N.py`)

This is a plain Python module. The skill-foundry section at the bottom is the **only thing
that changes between projects**. Everything in `skills/` stays untouched.

### Required fields in `config/project_N.py`

```python
# ── Required by foundry ────────────────────────────────────────────────────────

RESPONDENT_TABLE = "fact_respondents"   # table used as denominator in all % calculations

SHARED_VIEW_COLS = (                    # injected at the end of every capability's VIEW section
    "  + shared across all views: gender, age, age_band, city_name, zone_name, ..."
)

CAPABILITIES: dict = {
    "awareness": {
        "view":           "v_brand_awareness",   # ← your actual view name
        "view_rows":      "39,842",              # for the LLM's benefit, approximate is fine
        "entity_col":     "brand_name",
        "stage_col":      "stage",
        "tom_value":      "TOM",
        "spont_value":    "SPONT",
        "aided_value":    "AIDED",
        "exclude_filter": "brand_name != 'Don''t Know / None'",
        "tom_desc":       "top of mind — single brand first recalled",
        "spont_desc":     "spontaneous multi-select, ordered",
        "aided_desc":     "aided recall from shown list",
    },
    "nps": {
        "view":           "v_brand_nps",
        "view_rows":      "10,200",
        "entity_col":     "brand_name",
        "score_col":      "nps_score",
        "category_col":   "nps_category",
        "promoter_min":   9,
        "passive_min":    7,
        "passive_max":    8,
        "detractor_max":  6,
        "min_raters":     50,
        "sparse_note":    "Respondents only rate brands they have personally used.",
    },
    # ... other capabilities
}

# ── Routing configuration ──────────────────────────────────────────────────────

SKILL_PRIORITY: list[str] = ["nps", "purchase", "room", "ownership", "awareness", "demographic"]
# Put more specific / unambiguous skills first to avoid false matches.

KEYWORDS: dict[str, list[str]] = {
    "nps":       ["nps", "net promoter", "promoter", "detractor", ...],
    "awareness": ["tom", "top of mind", "recall", "awareness", ...],
    # ...
}

ENTITY_KEYWORDS: list[str] = ["bajaj", "crompton", ...]  # brand/product names
ENTITY_SKILL = "awareness"   # which skill entity keywords route to

# ── UI metadata ────────────────────────────────────────────────────────────────

SKILL_META: dict = {
    "awareness":   {"label": "Brand Awareness",   "icon": "📢"},
    "nps":         {"label": "NPS / Ratings",     "icon": "⭐"},
    # ...
    "general":     {"label": "General",           "icon": "🔍"},
}
```

---

## Routing Logic (`skills/foundry.py → route_query`)

Zero API calls. Pure keyword matching.

```
Question arrives
      │
      ▼
1. Scan SKILL_PRIORITY in order
   For each skill: any keyword in KEYWORDS[skill] found in question?
   → return that skill immediately (first match wins)
      │
      ▼ (no match)
2. Check ENTITY_KEYWORDS (brand / product names)
   Any entity name found in question?
   → return ENTITY_SKILL (usually "awareness")
      │
      ▼ (no match)
3. Check follow-up pronouns ("their", "those", "same", "it", "them")
   AND prior_skill is known from previous turn?
   → return prior_skill (carry forward context)
      │
      ▼ (no match)
4. Fall back to "general"
   → returns overview of ALL views (~900 tokens)
```

Priority order matters. `"purchase"` must come before `"ownership"` because questions like
"what appliances were bought" contain "bought" (purchase keyword) but also might trigger
ownership keywords. Put the more specific skill first.

---

## Prompt Cache (`skills/foundry.py → build_prompt_cache`)

At Streamlit startup (before the first user message), all skill prompts are assembled once
and stored in a dict in module scope:

```python
PROMPT_CACHE: dict[str, str] = build_prompt_cache(project)
```

This means:
- Zero latency per question for prompt assembly
- Zero tokens wasted if the same skill is used multiple times
- If a capability fails to assemble (misconfigured binding), it prints a warning and is
  skipped — the "general" fallback is always included

`get_sql()` in `views/chat.py` does:
```python
system_prompt = PROMPT_CACHE.get(skill_key, PROMPT_CACHE["general"])
```

---

## Adding a new capability

1. Create `skills/capabilities/your_capability.py` following the interface above.
2. Register it in `skills/capabilities/__init__.py`:
   ```python
   from skills.capabilities import your_capability
   REGISTRY["your_capability"] = your_capability
   ```
3. Add the binding dict to `config/project_N.CAPABILITIES["your_capability"]`.
4. Add keyword list to `config/project_N.KEYWORDS["your_capability"]`.
5. Add `"your_capability"` to `config/project_N.SKILL_PRIORITY` at the right position.
6. Add UI entry to `config/project_N.SKILL_META`.

No changes to `skills/foundry.py`, `skills/base_rules.py`, or `views/chat.py`.

---

## Adding a new project

1. Duplicate `config/project_1.py` as `config/project_2.py` (or `config/biryani.py`).
2. Change `PROJECT_ID`, `PROJECT_NAME`, `DATA_FILE`, `SHEET_NAME`.
3. Update `DIMENSIONS` with the new survey's code → label mappings.
4. Update `CAPABILITIES` with the new project's actual view/column names.
5. Update `KEYWORDS` and `ENTITY_KEYWORDS` for the new domain.
6. Register in `config/registry.py`.

**The `skills/` directory does not change at all.** The NPS capability works for any
survey that has a 0-10 recommendation score column. The awareness capability works for any
survey with TOM/SPONT/AIDED stages. You are only describing WHERE those things are in your
new project's database — not rewriting the business logic.

### Example: biryani brand preference survey

```python
# config/biryani.py
PROJECT_ID   = "biryani"
PROJECT_NAME = "Biryani Brand Preference — Urban India 2026"

CAPABILITIES = {
    "awareness": {
        "view":           "v_biryani_brand_awareness",
        "entity_col":     "brand_name",
        "stage_col":      "recall_stage",
        "tom_value":      "TOP_OF_MIND",
        "spont_value":    "SPONTANEOUS",
        "aided_value":    "AIDED",
        # ... rest of bindings
    },
    "nps": {
        "view":           "v_biryani_nps",
        "score_col":      "recommend_score",   # ← different column name, same concept
        "promoter_min":   9,
        "detractor_max":  6,
        # ...
    },
}
```

The `awareness.py` and `nps.py` capability files are unchanged.
The new project gets brand awareness + NPS analysis for free.

---

## Why Python files, not Markdown?

Capability files are `.py` not `.md` because they contain **executable logic**:
- `format_prompt(binding, shared_cols, respondent_table)` receives a dict of your
  project's column names and **dynamically substitutes** them into the prompt template.
- `KEY_COLUMNS_SUMMARY` is a Python format string: `"{entity_col}, nps_score"` —
  it expands when formatted with the binding dict.

An `.md` file is static text. It cannot do `f"SELECT * FROM {binding['view']}"`.
You would need a custom template parser, which would be more code for no benefit.

The Layer 3 bindings in `config/project_N.py` ARE the "per-project config file" — it is
the only file you touch when onboarding a new project. The Python capability files in
`skills/capabilities/` are shared infrastructure that you never change unless the
underlying business concept changes (e.g., the industry adopts a new NPS scale).

---

## Token budget summary

| Skill | View schema sent | Estimated tokens |
|---|---|---|
| nps | v_brand_nps + NPS formula | ~500 |
| awareness | v_brand_awareness + funnel rules | ~550 |
| ownership | v_kitchen_ownership + entity list | ~380 |
| purchase | v_recent_purchase + rank rules | ~400 |
| room | v_room_appliances + entity list | ~380 |
| demographic | v_respondents + geo rules | ~450 |
| general (fallback) | Overview of all 6 views | ~900 |

Layer 1 rules (~200 tokens) are included in every skill's total above.

Prior conversation context (last 4 turns, Q+SQL only, no result rows): ~400 tokens max.

**Total per SQL call: ~600–1,300 tokens. Was 6,500 tokens before the foundry was built.**
