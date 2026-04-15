"""
Chat page — natural language → SQL → visualisation.
Uses the Skill Foundry (skills/foundry.py) for zero-token routing and prompt assembly.

v2 Enhancements:
  - Thinker: complexity classifier + LLM planner for multi-step queries
  - Comparison engine: auto-detects leader/runner-up/delta
  - Contextual insights: benchmark-driven domain interpretation
  - Chart renderer: chart_spec-driven + heuristic fallback
"""

import os
import re
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

# ── project + foundry imports ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

import sys
sys.path.insert(0, str(BASE_DIR))

from config import project_1 as project
from skills.foundry import route_query, build_prompt_cache
from skills.thinker import (
    classify_complexity, plan_query, execute_plan,
    build_session_context, QueryPlan,
)
from skills.capabilities.compare import should_compare, build_comparison
from skills.capabilities.insights import get_benchmark_context, build_enriched_prompt
from views.chart_renderer import (
    render_result, render_table, parse_chart_spec,
)

# ── constants ─────────────────────────────────────────────────────────────────-
# Use db_loader to get database - downloads on each session if needed
from db_loader import get_db_path
DB_PATH = get_db_path()

if not DB_PATH or not DB_PATH.exists():
    print("WARNING: Could not initialize database")

groq_client   = Groq(api_key=os.environ.get("GROQ_API_KEY", "missing_key"))
SQL_MODEL     = "llama-3.1-8b-instant"        # Fast, cheap — good enough for SQL gen
SUMMARY_MODEL = "llama-3.1-8b-instant"        # Fast, cheap — summary with pre-computed context
THINKER_MODEL = "qwen/qwen3-32b"              # Reasoning model for complex query planning
FALLBACK_MODEL = "llama-3.3-70b-versatile"    # Fallback if Qwen3 fails
CONTEXT_TURNS = 4

# Pre-assemble all skill prompts once at startup (pure Python, 0 tokens)
PROMPT_CACHE: dict[str, str] = build_prompt_cache(project)
SKILL_META:   dict           = project.SKILL_META
BENCHMARKS:   dict           = project.BENCHMARKS


# ── LLM helpers ────────────────────────────────────────────────────────────────

def _strip_sql_comments(sql: str) -> str:
    return "\n".join(l for l in sql.split("\n") if not l.strip().startswith("--")).strip()


def _extract_sql(response: str) -> str:
    """Extract SQL query from LLM response that may include explanation."""
    sql = re.sub(r"^```(?:sql)?\s*", "", response.strip(), flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    match = re.search(r"(SELECT\s+.+)", sql, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return sql


def get_sql(question: str, skill_key: str, history: list[dict]) -> str:
    """Generate SQL using the cached skill prompt + conversation context.
    Returns raw LLM output (may contain CHART: spec line).
    Falls back to Gemini if Groq fails."""
    system_prompt = PROMPT_CACHE.get(skill_key, PROMPT_CACHE["general"])

    messages = [{"role": "system", "content": system_prompt}]

    # Inject last N Q&A pairs (Q + SQL only — no result rows, see BUG-008)
    pairs = []
    for msg in history:
        if msg["role"] == "user":
            pairs.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant" and msg.get("sql"):
            pairs.append({"role": "assistant", "content": msg["sql"]})
    for msg in pairs[-(CONTEXT_TURNS * 2):]:
        messages.append(msg)

    messages.append({"role": "user", "content": question})

    # Try Groq first
    try:
        r = groq_client.chat.completions.create(
            model=SQL_MODEL, messages=messages, temperature=0.0, max_tokens=512,
        )
        raw = r.choices[0].message.content or ""
        return raw.strip()
    except Exception as groq_error:
        # Fallback to Gemini if Groq fails
        print(f"Groq failed ({groq_error}), trying Gemini fallback...")
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(
                system_prompt + "\n\n" + "Question: " + question + "\n\nGenerate SQL query only, no explanation."
            )
            return response.text.strip()
        except Exception as gemini_error:
            print(f"Gemini fallback also failed: {gemini_error}")
            raise groq_error


def _process_sql_output(raw: str) -> tuple[str, dict]:
    """Process raw LLM output: extract SQL + chart_spec, clean SQL."""
    sql, chart_spec = parse_chart_spec(raw)
    sql = _extract_sql(sql)
    sql = _strip_sql_comments(sql)
    return sql, chart_spec


def run_sql(sql: str) -> tuple[pd.DataFrame | None, str | None]:
    try:
        con = sqlite3.connect(str(DB_PATH))
        df  = pd.read_sql_query(sql, con)
        con.close()
        return df, None
    except Exception as e:
        return None, str(e)


def _llm_call(system_prompt: str, user_prompt: str) -> str:
    """LLM call for the Thinker planner — uses reasoning model cascade.

    Cascade: Qwen3-32B (thinking) → Llama-3.3-70B → Gemini Flash.
    The thinking model produces better decomposition plans because it
    reasons through the query structure before outputting JSON.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Tier 1: Qwen3-32B (reasoning/thinking model)
    try:
        r = groq_client.chat.completions.create(
            model=THINKER_MODEL,
            messages=messages,
            temperature=0.6,   # Qwen3 recommended: 0.6 for thinking
            max_tokens=1024,   # More room for reasoning + JSON output
        )
        content = (r.choices[0].message.content or "").strip()
        # Qwen3 may wrap thinking in <think>...</think> tags — extract the answer
        if "</think>" in content:
            content = content.split("</think>", 1)[-1].strip()
        if content:
            print(f"[Thinker] Qwen3-32B succeeded")
            return content
    except Exception as e:
        print(f"[Thinker] Qwen3-32B failed: {e}")

    # Tier 2: Llama-3.3-70B (strong general model)
    try:
        r = groq_client.chat.completions.create(
            model=FALLBACK_MODEL,
            messages=messages,
            temperature=0.0, max_tokens=512,
        )
        content = (r.choices[0].message.content or "").strip()
        if content:
            print(f"[Thinker] Llama-3.3-70B succeeded (fallback)")
            return content
    except Exception as e:
        print(f"[Thinker] Llama-3.3-70B failed: {e}")

    # Tier 3: Gemini Flash (last resort)
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(system_prompt + "\n\n" + user_prompt)
        print(f"[Thinker] Gemini Flash succeeded (last resort)")
        return response.text.strip()
    except Exception as e:
        print(f"[Thinker] All models failed. Last error: {e}")
        return ""


def plain_english_answer(question: str, df: pd.DataFrame,
                         skill_key: str = "", chart_spec: dict | None = None) -> str:
    """Generate an enriched plain English summary with comparison + benchmark context.
    Falls back to Gemini if Groq fails."""
    # Build comparison context (0 tokens — pure Python)
    comparison_summary = ""
    if should_compare(df, question):
        comp = build_comparison(df, question)
        if comp:
            comparison_summary = comp.to_context_string()

    # Build benchmark context (0 tokens — pure Python)
    benchmark_context = get_benchmark_context(df, skill_key, question, BENCHMARKS)

    # Build enriched prompt (~300 tokens vs original ~200)
    prompt = build_enriched_prompt(
        question, df,
        comparison_summary=comparison_summary,
        benchmark_context=benchmark_context,
    )

    # Try Groq first
    try:
        r = groq_client.chat.completions.create(
            model=SUMMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=300,
        )
        return r.choices[0].message.content.strip()
    except Exception as groq_error:
        # Fallback to Gemini
        print(f"Groq failed for summary ({groq_error}), trying Gemini fallback...")
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as gemini_error:
            print(f"Gemini summary fallback also failed: {gemini_error}")
            return "Summary generation failed."


# ── simple flow handler ────────────────────────────────────────────────────────

def _handle_simple_query(question: str, skill_key: str, history: list[dict]) -> dict:
    """Handle a simple single-skill query (the standard flow)."""
    meta = SKILL_META.get(skill_key, {"icon": "🔍", "label": skill_key})
    st.caption(f"{meta['icon']} Skill: **{meta['label']}**")

    with st.spinner("Generating SQL..."):
        try:
            raw_output = get_sql(question, skill_key, history)
            sql, chart_spec = _process_sql_output(raw_output)
            sql_error = None
        except Exception as e:
            sql, chart_spec, sql_error = None, {"type": "auto"}, str(e)

    if sql_error:
        st.error(f"LLM error: {sql_error}")
        return {
            "role": "assistant", "content": f"LLM error: {sql_error}",
            "sql": None, "df": None, "error": sql_error,
            "question": question, "skill": skill_key,
        }

    with st.expander("Generated SQL", expanded=True):
        st.code(sql, language="sql")

    with st.spinner("Running query..."):
        df, error = run_sql(sql)

    # Auto-retry with general on SQL error
    if error and skill_key != "general":
        st.warning("Retrying with General skill…")
        try:
            raw2 = get_sql(question, "general", history)
            sql2, chart_spec2 = _process_sql_output(raw2)
            df2, error2 = run_sql(sql2)
            if not error2 and df2 is not None:
                sql, df, error, skill_key, chart_spec = sql2, df2, None, "general", chart_spec2
                with st.expander("Retry SQL (General)", expanded=True):
                    st.code(sql, language="sql")
        except Exception:
            pass

    if error:
        st.error(f"SQL error: {error}")
        return {
            "role": "assistant", "content": f"SQL error: {error}",
            "sql": sql, "df": None, "error": error,
            "question": question, "skill": skill_key,
        }

    # Render chart using chart_spec
    render_result(df, question, chart_spec=chart_spec)

    # Enriched summary with comparison + benchmarks
    with st.spinner("Analysing..."):
        answer = (plain_english_answer(question, df, skill_key, chart_spec)
                  if (df is not None and not df.empty)
                  else "No results.")
        note = f"*{len(df)} row(s) · skill: {skill_key}*" if df is not None else ""
    st.markdown(answer)
    st.caption(note)

    return {
        "role": "assistant", "content": answer,
        "sql": sql, "df": df, "error": None,
        "question": question, "skill": skill_key,
    }


# ── complex flow handler (thinker) ────────────────────────────────────────────

def _handle_complex_query(question: str, history: list[dict]) -> dict:
    """Handle a complex multi-step query using the Thinker."""
    st.caption("🧠 **Deep Analysis** — decomposing into sub-queries...")

    # Build session context for the planner
    session_ctx = build_session_context(history)

    # Plan the decomposition
    with st.spinner("🧠 Planning analysis steps..."):
        plan = plan_query(question, session_ctx, _llm_call)

    # Show the plan
    if plan.reasoning:
        with st.expander("🧠 Analysis Plan", expanded=True):
            st.markdown(f"**Reasoning:** {plan.reasoning}")
            for step in plan.steps:
                dep = f" (depends on step {step.depends_on})" if step.depends_on else ""
                st.markdown(f"  {step.step_id}. **[{step.skill}]** {step.sub_question}{dep}")
            st.caption(f"Merge strategy: `{plan.merge_strategy}` · Chart hint: `{plan.chart_hint}`")

    # Execute all steps
    def _get_sql_for_step(q, skill, hist):
        raw = get_sql(q, skill, hist)
        sql, _ = _process_sql_output(raw)
        return sql

    with st.spinner(f"Running {len(plan.steps)} sub-queries..."):
        result = execute_plan(plan, _get_sql_for_step, run_sql, history)

    # Show individual SQL queries
    for i, sql in enumerate(result.all_sqls):
        step = plan.steps[i] if i < len(plan.steps) else None
        label = f"SQL #{i+1}: [{step.skill if step else '?'}] {step.sub_question[:50] if step else ''}..."
        with st.expander(label, expanded=False):
            st.code(sql, language="sql")

    if result.error and result.df is None:
        st.error(f"Query error: {result.error}")
        return {
            "role": "assistant", "content": f"Analysis error: {result.error}",
            "sql": "; ".join(result.all_sqls), "df": None, "error": result.error,
            "question": question, "skill": ",".join(result.skill_keys),
        }

    # Render merged result
    chart_spec = {"type": result.chart_hint} if result.chart_hint != "auto" else None
    if result.df is not None and not result.df.empty:
        if result.merge_description:
            st.caption(f"📊 {result.merge_description}")
        render_result(result.df, question, chart_spec=chart_spec)

    # Enriched summary
    primary_skill = result.skill_keys[0] if result.skill_keys else "general"
    with st.spinner("Synthesising insights..."):
        answer = (plain_english_answer(question, result.df, primary_skill, chart_spec)
                  if (result.df is not None and not result.df.empty)
                  else "No results found.")
        total_rows = len(result.df) if result.df is not None else 0
        note = f"*{total_rows} row(s) · {len(result.all_sqls)} queries · skills: {', '.join(result.skill_keys)}*"
    st.markdown(answer)
    st.caption(note)

    return {
        "role": "assistant", "content": answer,
        "sql": "; ".join(result.all_sqls), "df": result.df, "error": None,
        "question": question, "skill": ",".join(result.skill_keys),
    }


# ── summary handler ───────────────────────────────────────────────────────────

def _handle_summary(question: str, history: list[dict]) -> dict:
    """Handle a session summary request (no SQL needed)."""
    st.caption("📝 **Session Summary**")

    # Build context from conversation history
    session_ctx = build_session_context(history, max_turns=10)

    prompt = (
        f"User asked: {question}\n\n"
        f"Session history:\n{session_ctx}\n\n"
        "Provide a clear, structured summary of the key findings from this conversation. "
        "Use bullet points. Reference specific numbers from prior answers."
    )

    with st.spinner("Generating summary..."):
        try:
            r = groq_client.chat.completions.create(
                model=SUMMARY_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=500,
            )
            answer = r.choices[0].message.content.strip()
        except Exception:
            answer = "Unable to generate summary."

    st.markdown(answer)

    return {
        "role": "assistant", "content": answer,
        "sql": None, "df": None, "error": None,
        "question": question, "skill": "summary",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE
# ═══════════════════════════════════════════════════════════════════════════════

st.title("OxData — Research Intelligence")
st.caption(
    f"{project.PROJECT_NAME} · {project.PROJECT_ID} · "
    "Apr–Jun 2021 · 6,631 respondents"
)

with st.sidebar:
    st.markdown("#### Skills (auto-routed, 0 tokens)")
    for key, meta in SKILL_META.items():
        kws = ", ".join(project.KEYWORDS.get(key, [])[:3])
        if kws:
            kws += "…"
        st.markdown(
            f"{meta['icon']} **{meta['label']}**  \n"
            f"<span style='color:#94A3B8;font-size:11px'>{kws}</span>",
            unsafe_allow_html=True,
        )
    st.divider()
    st.markdown("#### 🧠 Thinker (auto-detected)")
    st.markdown(
        "<span style='color:#94A3B8;font-size:11px'>"
        "Multi-domain questions auto-decomposed into sub-queries"
        "</span>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption(f"SQL: `{SQL_MODEL}` · Thinker: `{THINKER_MODEL}` · Context: {CONTEXT_TURNS} turns")
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages   = []
        st.session_state.last_skill = None
        st.rerun()

with st.sidebar:
    st.divider()
    st.markdown("#### 🔑 API Keys")
    if "groq_key" not in st.session_state:
        st.session_state.groq_key = os.environ.get("GROQ_API_KEY", "")
    
    groq_key = st.text_input("Groq API Key", type="password", value=st.session_state.groq_key, placeholder="Enter your Groq key")
    
    if groq_key:
        st.session_state.groq_key = groq_key
        os.environ["GROQ_API_KEY"] = groq_key
        groq_client = Groq(api_key=groq_key)

if "messages"   not in st.session_state:
    st.session_state.messages   = []
if "last_skill" not in st.session_state:
    st.session_state.last_skill = None

# Replay history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            skill = msg.get("skill", "")
            if skill and skill in SKILL_META:
                meta = SKILL_META[skill]
                st.caption(f"{meta['icon']} Skill: **{meta['label']}**")
            elif "," in str(skill):
                st.caption(f"🧠 **Deep Analysis** — skills: {skill}")
            if msg.get("sql"):
                with st.expander("Generated SQL", expanded=False):
                    st.code(msg["sql"], language="sql")
            if msg.get("df") is not None:
                render_result(msg["df"], msg.get("question", ""))
            if msg.get("error"):
                st.error(f"SQL error: {msg['error']}")
            if msg.get("content"):
                st.markdown(msg["content"])
        else:
            st.markdown(msg["content"])

# Handle new input
if question := st.chat_input("Ask about brands, NPS, appliances, respondents…"):
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("assistant"):
        # Classify complexity (0 tokens — Python)
        complexity = classify_complexity(question, st.session_state.messages)

        if complexity == "summary":
            msg = _handle_summary(question, st.session_state.messages[:-1])

        elif complexity == "complex":
            msg = _handle_complex_query(question, st.session_state.messages[:-1])

        else:
            # "simple" or "contextual" — use standard single-skill flow
            skill_key = route_query(question, project, st.session_state.last_skill)
            msg = _handle_simple_query(question, skill_key, st.session_state.messages[:-1])

        # Update state
        st.session_state.last_skill = msg.get("skill")
        st.session_state.messages.append(msg)
