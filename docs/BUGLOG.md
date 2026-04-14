# Bug Log — OxData Project

Format per entry:
- **ID** — BUG-XXX
- **Date** — when found
- **Severity** — Critical / High / Medium / Low
- **Status** — Open / Fixed / Won't Fix / Deferred
- **Symptom** — what the user/dev saw
- **Root Cause** — why it happened
- **Fix** — what was changed
- **Files Changed** — exact files
- **Prevention** — how to avoid in future

---

## BUG-001 — Gemini 429 Quota Exhausted
- **Date:** 2026-04-11
- **Severity:** Critical (app unusable)
- **Status:** Fixed
- **Symptom:**
  ```
  google.api_core.exceptions.ResourceExhausted: 429
  Quota exceeded for metric: generativelanguage.googleapis.com/
  generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash
  ```
  App crashed on every query. Error at `app.py:155 → get_sql() → model.generate_content()`
- **Root Cause:**
  Gemini 2.0 Flash free tier daily request quota (RPD) was fully exhausted.
- **Fix:**
  Replaced `google-generativeai` with `groq` SDK. New model: `llama-3.3-70b-versatile`.
  Both `get_sql()` and `plain_english_answer()` now use `groq_client.chat.completions.create()`.
- **Files Changed:** `app.py`, `requirements.txt`
- **Prevention:** Check free tier limits before committing. Add model fallback chain.

---

## BUG-002 — Unicode Encode Error in ETL (Windows cp1252)
- **Date:** 2026-04-10
- **Severity:** Medium (ETL crashed, blocked DB build)
- **Status:** Fixed
- **Symptom:**
  ```
  UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 22
  ```
- **Root Cause:**
  ETL used `→` (U+2192) and `✓` (U+2713) in print statements. Windows default console
  encoding is cp1252 which doesn't support these characters.
- **Fix:** Changed `→` to ` to ` and `✓` to plain `Done.`
- **Files Changed:** `etl/load_data.py`
- **Prevention:** On Windows, use ASCII-safe characters or set `PYTHONUTF8=1`.

---

## BUG-003 — File Copy Failure (bash cp with Windows paths)
- **Date:** 2026-04-10
- **Severity:** Medium (setup blocked)
- **Status:** Fixed
- **Symptom:** `cp` command failed with Windows-style paths containing spaces.
- **Root Cause:** bash `cp` doesn't handle Windows paths with spaces and backslashes.
- **Fix:** Replaced with Python `shutil.copy2()` and `shutil.copytree()`.
- **Prevention:** Always use Python `pathlib` + `shutil` for file ops on Windows.

---

## BUG-004 — choices Table Missing in lens.db (legacy)
- **Date:** 2026-04-10
- **Severity:** High (analytics crashed in legacy system)
- **Status:** Fixed in legacy; design eliminated in oxdata rebuild
- **Symptom:** `OperationalError: no such table: choices`
- **Root Cause:** `choices` table never created during original migration.
- **Fix:** Read from `OX - Datamap.xlsx` choices sheet, created + populated table (529 rows).
- **Note:** Superseded by oxdata rebuild — `dim_brand` etc. replace choices table.

---

## BUG-005 — brand_map Lookup Used Wrong Question Code (legacy)
- **Date:** 2026-04-10
- **Severity:** High (brand names all empty in legacy system)
- **Status:** Fixed in legacy; eliminated in oxdata rebuild
- **Symptom:** `brand_funnel_deep_dive()` returned empty brand names for all rows.
- **Root Cause:** `_get_choice_map("bq1c")` called but bq1c has no labelled choices.
  Should have been `bq1a`.
- **Fix:** Changed to `_get_choice_map("bq1a")`.
- **Note:** Impossible in oxdata — `dim_brand` is single source, JOINed in every view.

---

## BUG-006 — Detail Query Wrongly Renders as Line Chart
- **Date:** 2026-04-11
- **Severity:** High (wrong visualisation, confusing output)
- **Status:** Fixed
- **Screenshot evidence:** User screenshot showing "Respondent Id over Time" line chart
  with spaghetti lines — occurred when asking "tell me their details" after
  "how many respondents are from Patna?". Result had 440 rows with columns
  `respondent_id, resp_name, gender, age, age_band, zone_name, interview_date, interviewer`.
- **Root Cause:**
  `render_result()` time-series detection path (path 4) checked for any column containing
  "date" → found `interview_date`. Then picked `respondent_id` (first numeric column) as
  Y-axis. This is nonsensical — `respondent_id` is an ID, not a metric. The chart then
  plotted each respondent name as a separate coloured line over time, creating the spaghetti.
- **Fix:**
  Added a **detail-level guard** at the start of `render_result()`:
  ```python
  DETAIL_MARKERS = {'respondent_id', 'resp_name', 'device_id', 'interviewer'}
  if any(c in df.columns for c in DETAIL_MARKERS):
      _render_table(df)
      return
  ```
  If any ID/name column is present, the result is row-level respondent data → skip
  all chart detection → render table directly.
  Additionally added: time-series path now skips if any numeric column is an ID column
  (contains "id" suffix).
- **Files Changed:** `app.py` — `render_result()` function
- **Prevention:** Always check if numeric columns are IDs before charting. IDs should
  never be plotted as Y-axis values.

---

## BUG-007 — Bar Chart Not Rendering for Label+Count Result
- **Date:** 2026-04-11
- **Severity:** Medium (chart requested but not shown)
- **Status:** Fixed
- **Screenshot evidence:** User screenshot showing flat table for "top 5 cities by female
  by a chart" query. Result had `city_name, female_count` (5 rows). No Plotly chart
  appeared — only `st.dataframe` table was shown. Also note: the LLM added SQL comments
  containing pre-computed (hallucinated) results that didn't match actual DB values.
- **Root Cause (two issues):**
  1. **Plotly rendering failure:** `px.bar(..., color=y_col, color_continuous_scale="Blues")`
     was silently failing in this Streamlit/Plotly version combination. The `color=` parameter
     using the same column as the bar values caused a conflict with `color_continuous_scale`.
     No exception was raised — Streamlit just showed nothing.
  2. **LLM added comments to SQL output:** Despite the rule saying "return ONLY the SQL",
     the model appended `-- Chart: ...` comment block with fake pre-computed numbers that
     didn't match the actual DB. This is prompt non-compliance and a hallucination risk.
- **Fix:**
  1. Simplified `px.bar()` call — removed `color=y_col` and `color_continuous_scale`,
     used fixed `color_discrete_sequence=["#4A90D9"]` instead. Much more stable.
  2. Wrapped all Plotly chart rendering in `try/except` — on failure, shows warning
     and falls back to table. No more silent failures.
  3. Added SQL post-processing to strip comment blocks from model output.
  4. Added `user_wants_chart` flag: if question contains "chart"/"graph"/"plot",
     force bar chart rendering even if auto-detection threshold isn't met.
- **Files Changed:** `app.py` — `render_result()`, `get_sql()`, `_strip_sql_comments()`
- **Prevention:** Never use the same column for both bar length and color scale in plotly.
  Always wrap chart rendering in try/except. Reinforce in system prompt: absolutely no
  comments or pre-computation in SQL output.

---

## BUG-008 — Massive Token Waste in Every API Call (Performance)
- **Date:** 2026-04-11
- **Severity:** High (rate limits hit, cost waste, slow responses)
- **Status:** Fixed
- **Symptom:**
  Groq API logs show every SQL generation call sending **5,000-5,900 input tokens**
  for output of only 15-115 tokens. Input:Output ratio is ~60:1 — extremely inefficient.
  Rate limit errors (HTTP 429) visible in logs:
  ```
  Rate limit reached: Limit 12000 TPM, Used 8551, Requested 6288
  ```
  Also: summary calls sending full result as string — for 440-row results this is
  thousands of tokens in the summary prompt.
- **Root Cause:**
  The entire `SCHEMA.md` (~3,000 tokens) + `LOGIC.md` (~2,000 tokens) + query examples
  (~1,500 tokens) were loaded as raw file text and injected into the system prompt on
  EVERY API call. These files are written for human readability (tables, markdown headers,
  verbose descriptions) — not for token efficiency.
  Additionally, multi-turn context injection was passing full result dataframe previews
  (500+ tokens per prior turn).
- **Token breakdown before fix:**
  ```
  System prompt (SCHEMA.md + LOGIC.md + examples): ~6,000 tokens
  Prior turn context (question + SQL + result sample): ~300 tokens each
  User question: ~10-20 tokens
  Total per SQL call: ~6,500 tokens minimum
  ```
- **Fix:**
  1. Replaced full MD file injection with a **compact inline schema** (~600 tokens):
     - View names + key columns only (no full column tables)
     - Rules condensed to 8 bullet points
     - 3 example queries only (most common patterns)
  2. Context injection now passes: **question + SQL only** (no result preview rows)
     Result preview in context was not significantly helping the LLM resolve references
     but was adding 300-800 tokens per prior turn.
  3. Summary prompt now caps result at **5 rows** regardless of actual result size.
  4. Reduced `CONTEXT_TURNS` from 6 to 4 (8 message halves = ~800 tokens max context)
- **Token breakdown after fix:**
  ```
  System prompt (compact inline): ~800 tokens
  Prior turn context (Q + SQL only, 4 turns): ~400 tokens max
  User question: ~10-20 tokens
  Total per SQL call: ~1,200-1,400 tokens (was 6,500)
  Reduction: ~80%
  ```
- **Files Changed:** `app.py` — `SYSTEM_PROMPT`, `build_messages_for_sql()`,
  `plain_english_answer()`
- **Prevention:** Never inject human-readable documentation files directly into LLM prompts.
  Write a separate compact schema representation specifically for LLM consumption.
  Monitor token counts in API logs regularly.

---

## BUG-009 — Schema Explorer Page Not Visible in Sidebar
- **Date:** 2026-04-11
- **Severity:** High (feature invisible to user)
- **Status:** Fixed
- **Symptom:**
  Only the Chat page appeared in the Streamlit sidebar. The Schema Explorer page created
  at `pages/1_Schema_Explorer.py` was never shown. No error — just silently absent.
- **Root Cause:**
  Streamlit 1.56.0 deprecated automatic `pages/` directory discovery. The legacy method
  (putting files in `pages/` and having Streamlit auto-detect them) no longer works.
  New approach requires explicit `st.navigation()` declaration in the main `app.py`.
  Additionally: page files served via `st.navigation()` must NOT call `st.set_page_config()`
  (that call is reserved for `app.py` only) — it causes a `StreamlitAPIException` if
  called from a page file.
- **Fix:**
  1. Moved `pages/1_Schema_Explorer.py` → `views/schema.py` (alongside `views/chat.py`).
  2. Rewrote `app.py` as a navigation hub:
     ```python
     pg = st.navigation({
         "Analytics": [
             st.Page("views/chat.py",   title="Chat",            icon="💬", default=True),
             st.Page("views/schema.py", title="Schema Explorer", icon="🗂️"),
         ]
     })
     pg.run()
     ```
  3. Removed `st.set_page_config()` call from `views/schema.py` (only kept in `app.py`).
- **Files Changed:** `app.py`, `views/schema.py` (moved from `pages/`)
- **Prevention:** In Streamlit >= 1.36, always use `st.navigation()` for multi-page apps.
  Never call `st.set_page_config()` from page files — only from the top-level `app.py`.

---

## BUG-010 — ER Diagram Static / Not Interactable
- **Date:** 2026-04-11
- **Severity:** Medium (UX — diagram present but not responsive)
- **Status:** Fixed
- **Symptom:**
  Schema Explorer ER diagram rendered as a static Plotly scatter chart. Scrolling zoomed
  the browser page (not the diagram), right-click did nothing useful, nodes could not be
  dragged to rearrange, tooltips were basic Plotly hover boxes.
- **Root Cause:**
  Plotly scatter charts have limited interactivity — zoom/pan are global (not per-node),
  and there is no concept of draggable individual nodes or edge highlighting on hover.
  The `st.plotly_chart()` component also intercepts scroll events at the Streamlit level
  before they reach Plotly's zoom handler.
- **Fix:**
  Replaced Plotly scatter with a full **Cytoscape.js** graph rendered via
  `st.components.v1.html()`. Cytoscape provides:
  - Drag individual nodes to rearrange the layout
  - Scroll to zoom in/out on the diagram itself
  - Click-drag on empty canvas area to pan
  - Hover tooltip with technical name (`fact_brand_nps`), human name ("Brand NPS"),
    description, and live row count from DB
  - Connected edges highlight in blue when a node is hovered
  - Node labels show both human-readable name AND technical table name (two lines)
- **Files Changed:** `views/schema.py` — `build_er_diagram()` replaced with
  `render_er_diagram()` using `components.html()`
- **Prevention:** For interactive graph/network diagrams in Streamlit, use a JS library
  (Cytoscape, D3, vis.js) via `components.html()`. Plotly is suitable for charts,
  not for draggable node-edge graphs.

---

## BUG-011 — Purchase Skill Routing Miss for "buy" Verb Forms
- **Date:** 2026-04-11
- **Severity:** Low (falls back to general correctly, but wastes ~500 extra tokens)
- **Status:** Fixed
- **Symptom:**
  "What did people buy recently?" routed to `general` instead of `purchase`.
  Routing test: `route_query("what did people buy recently?", project)` → `"general"`.
- **Root Cause:**
  `KEYWORDS["purchase"]` only contained multi-word phrases: `"recently bought"`,
  `"recent buy"`, `"last bought"`. The question uses `"buy"` as a bare verb at the end
  of the phrase (`"did people buy recently"`) — no exact phrase match found.
  `" buy "` (with trailing space) also fails when `"buy"` appears at end of sentence.
- **Fix:**
  Changed `" buy "` → `" buy"` (no trailing space required) and added `"did buy"`,
  `"have bought"` to `KEYWORDS["purchase"]` in `config/project_1.py`.
  Now catches: "did buy", "they buy", "people buy", "have bought".
- **Files Changed:** `config/project_1.py` — `KEYWORDS["purchase"]`
- **Prevention:** Test keyword routing with verb form variations (buy/bought/buying/buy),
  not just the noun form (purchase/purchased). Trailing-space anchors fail at sentence end.

---

## Open / Tracked Issues

| ID | Description | Severity | Status |
|----|-------------|----------|--------|
| — | `category` (mq6) is NULL — not in source export | Medium | Deferred |
| — | `sec` (NCCS class) not computed | Medium | Deferred |
| — | Room-level data for mq2a not preserved | Low | Won't Fix |
| — | mq2a code 10 absent from codebook | Low | Won't Fix |
| — | mq3a code 15 blank in datamap | Low | Won't Fix |
| — | Groq free tier TPM limit can still be hit with large result summaries | Low | Monitored |
| BUG-012 | Groq API rate limit (100k TPD) blocks testing after ~35 questions | High | Open |
| BUG-013 | "breakdown by gender" routes to ownership instead of demographic | Medium | Open |

---

## BUG-012 — Groq API Rate Limit (100k TPD)
- **Date:** 2026-04-12
- **Severity:** High (test automation blocked)
- **Status:** Fixed
- **Symptom:**
  ```
  Error code: 429 - Rate limit reached for model `llama-3.3-70b-versatile` 
  on tokens per day (TPD): Limit 100000, Used 99530, Requested 761
  ```
- **Root Cause:**
  Groq free tier has a daily token limit (TPD) of 100,000 tokens.
- **Fix:** 
  - Added Gemini 2.0 Flash fallback in `get_sql()` and `plain_english_answer()`
  - App now auto-switches to Gemini when Groq fails
  - Added exponential backoff retry in test scripts
- **Files Changed:** `views/chat.py`
- **Prevention:** Auto-fallback prevents app from being unusable

---

## BUG-013 — Skill Routing: "breakdown by gender" → ownership
- **Date:** 2026-04-12
- **Severity:** Medium (incorrect routing)
- **Status:** Open
- **Symptom:**
  Question "Show me the breakdown by gender" incorrectly routes to "ownership" skill
  instead of "demographic" skill.
- **Root Cause:**
  Keyword conflict in SKILL_PRIORITY or KEYWORDS. Need to review why "gender" triggers 
  ownership instead of demographic.
- **Fix:** 
  - Review KEYWORDS in `config/project_1.py` for overlapping keywords
  - Adjust SKILL_PRIORITY order if needed
  - Add more specific keywords for demographic to distinguish
- **Files Changed:** `config/project_1.py`
- **Prevention:** Add more test cases to catch keyword conflicts
