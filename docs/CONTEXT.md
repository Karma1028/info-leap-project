# How Schema Context Is Passed to the API

This document explains exactly how the LLM knows about the database — what gets sent,
how much it costs in tokens, and why each design decision was made.

---

## The Problem: LLMs Don't Know Your Database

Groq has no idea your database has a table called `v_brand_awareness` or that
`stage = 'TOM'` means top-of-mind awareness. Every question must arrive with enough
context for the LLM to write correct SQL.

The challenge: **more context = more tokens = more cost + slower responses.**

---

## What Gets Sent Per Request

Every SQL-generation API call sends three things:

```
┌─────────────────────────────────────────────────────────┐
│ 1. SYSTEM PROMPT (assembled from Skill Foundry)         │
│    Layer 1 rules + skill-specific schema slice           │
│    Token cost: ~350–900 tokens (varies by skill)         │
├─────────────────────────────────────────────────────────┤
│ 2. CONVERSATION CONTEXT (last 4 turns, Q+SQL only)      │
│    Prior questions + the SQL they generated              │
│    Token cost: ~0–400 tokens (grows with session)        │
├─────────────────────────────────────────────────────────┤
│ 3. YOUR QUESTION (current message)                      │
│    Token cost: ~10–30 tokens                            │
└─────────────────────────────────────────────────────────┘
Total: ~400–1,300 tokens per SQL call
Output: ~50–120 tokens (SQL is short)
```

---

## 1. System Prompt — The Skill Foundry

### Why Not Load the Full SCHEMA.md?

`SCHEMA.md` is human-readable documentation (~3,000 tokens). Injecting it raw into every
API call was sending 5,000-6,500 tokens per request and hitting Groq's rate limits.
(See **BUG-008** in BUGLOG.md.)

### The Three-Layer Architecture

System prompts are assembled from three layers that are separated by concern:

```
Layer 1: base_rules.py      — Universal SQL rules (same for ALL projects/skills)
Layer 2: capabilities/*.py  — Domain business logic (NPS formula, awareness funnel)
Layer 3: config/project_N.py — Project schema bindings (view names, column names)
```

The foundry (`skills/foundry.py`) assembles these at startup into per-skill prompt strings
stored in `PROMPT_CACHE`. No assembly work happens during a user question.

### Skill routing (zero API tokens)

The router classifies each question by keyword matching — no API calls:

```
Question arrives
  → scan SKILL_PRIORITY keyword lists (first match wins)
  → check ENTITY_KEYWORDS (brand/product names)
  → check follow-up pronouns + prior_skill
  → fallback: "general" (all views, compact overview)
```

| Skill | Schema loaded | Est. tokens | Triggered by |
|---|---|---|---|
| nps | v_brand_nps + NPS formula | ~500 | "nps", "promoter", "recommend"… |
| awareness | v_brand_awareness + funnel | ~550 | "TOM", "recall", "funnel"… |
| ownership | v_kitchen_ownership | ~380 | "kitchen", "mixer", "owned"… |
| purchase | v_recent_purchase | ~400 | "purchased", "bought"… |
| room | v_room_appliances | ~380 | "fan", "AC", "bulb", "geyser"… |
| demographic | v_respondents | ~450 | "city", "gender", "how many"… |
| general (fallback) | All 6 views (compact) | ~900 | No keyword match |

### Are Skills Project-Specific?

**No — capability logic is shared across all projects.** This is a key design goal.

The `skills/capabilities/*.py` files contain domain concepts (NPS calculation, awareness
funnel structure) in parameterised form. They never reference a specific view name or
column name.

The `config/project_N.py` file provides the bindings: which view, which column, which
threshold values. This is the ONLY file that changes between projects.

For full details: see `docs/SKILLS.md`.

---

## 2. Conversation Context — Follow-Up Resolution

### The Problem

If you ask "How many respondents are from Patna?" and then "Show their age breakdown",
the LLM needs to know "their" = respondents from Patna.

### The Solution

The last 4 Q&A pairs are passed in the messages array. Each prior assistant message
carries the SQL that was generated — not the result rows:

```python
messages = [
    {"role": "system",    "content": skill_prompt},
    # Prior turns injected here:
    {"role": "user",      "content": "How many respondents from Patna?"},
    {"role": "assistant", "content": "SELECT COUNT(*) FROM v_respondents WHERE city_name='Patna'"},
    # Current question:
    {"role": "user",      "content": "Show their age breakdown"},
]
```

The LLM sees the prior SQL with `WHERE city_name='Patna'` and carries that filter forward.

### Why No Result Rows in Context?

Early version injected result row samples in context: `"[440 rows returned. Sample: ...]"`.
This added 300-800 tokens per prior turn for zero benefit — the SQL alone is sufficient
for the LLM to resolve follow-up references. (See **BUG-008** in BUGLOG.md.)

### Last-Skill Carry-Forward

`st.session_state.last_skill` tracks which skill was used for the previous question.
When a follow-up pronoun is detected AND no keyword matches a new skill, the same skill
is reused — ensuring the follow-up gets the same schema context as the original.

---

## 3. Summary Generation — Separate Call

After the SQL runs, a second lighter API call generates a plain-English answer:

```
Input:  question + first 5 rows of result
Output: 2–3 sentence summary
Tokens: ~150–250 input, ~80–120 output
```

Only 5 rows are sent regardless of how many were returned. The LLM only needs enough
rows to see the pattern — sending all 440 rows would be thousands of tokens.

---

## 4. Token Budget Summary

| Version | Input Tokens/Call | Why |
|---|---|---|
| v1 (Gemini, full SCHEMA.md + LOGIC.md) | ~6,500 | Entire MD files loaded raw |
| v2 (Groq, compact inline prompt) | ~1,200 | Single compact prompt, all views |
| v3 (Groq, Skill Foundry) | ~400–1,300 | Skill-specific slice only |

**Groq free tier limits** (`llama-3.3-70b-versatile`):
- 12,000 TPM (tokens per minute), 14,400 RPD (requests per day)
- At ~700 tokens/call average: ~17 calls/minute before TPM limit

---

## 5. Why Pre-Joined Views Are Critical

Without views, the system prompt must describe all join keys, and the LLM must write
multi-table JOINs — more complexity, more hallucination risk, more tokens.

```sql
-- Without views (LLM must write and remember all joins)
SELECT db.brand_name, COUNT(*) FROM fact_brand_awareness fba
JOIN dim_brand db ON fba.brand_id = db.brand_id
JOIN fact_respondents fr ON fba.respondent_id = fr.respondent_id
JOIN dim_city dc ON fr.city_id = dc.city_id
WHERE dc.city_name = 'Mumbai' GROUP BY db.brand_name

-- With views (LLM writes this instead)
SELECT brand_name, COUNT(*) FROM v_brand_awareness
WHERE city_name = 'Mumbai' GROUP BY brand_name
```

Simpler SQL = fewer errors + less schema to describe in the prompt.

---

## Files Involved

| File | Role |
|---|---|
| `skills/base_rules.py` | Layer 1 — universal SQL rules for every project/skill |
| `skills/capabilities/*.py` | Layer 2 — domain logic templates (NPS, awareness, etc.) |
| `skills/foundry.py` | Assembler + keyword router + prompt cache builder |
| `config/project_1.py` | Layer 3 — project schema bindings (view names, columns) |
| `views/chat.py` | UI — calls `route_query()` and `build_prompt_cache()` at startup |
| `docs/SCHEMA.md` | Human-readable schema (NOT injected into API) |
| `docs/LOGIC.md` | Human-readable business logic (NOT injected into API) |
| `docs/SKILLS.md` | Foundry architecture and developer guide |
