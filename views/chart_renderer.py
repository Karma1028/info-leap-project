"""
Chart Renderer — All Visualisation Logic (Extracted from chat.py)
=================================================================
Provides two modes:
  1. **chart_spec-driven** — LLM returns a JSON spec alongside SQL; we render exactly
     what was requested (bar, funnel, pie, grouped_bar, nps_waterfall, etc.)
  2. **heuristic fallback** — if chart_spec is absent or ``{"type": "auto"}``, the
     original column-name heuristic logic selects the best chart.

Public API:
  parse_chart_spec(raw_output)  → (sql, chart_spec_dict)
  render_result(df, question, chart_spec=None)  → None  (renders via st.*)
  render_table(df)              → None  (formatted st.dataframe)
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ═══════════════════════════════════════════════════════════════════════════════
# CHART SPEC PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def parse_chart_spec(raw_output: str) -> tuple[str, dict]:
    """
    Split LLM output into SQL and chart_spec.

    The LLM is instructed to append a ``CHART: {...}`` line after the SQL.
    If missing or malformed, falls back to ``{"type": "auto"}``.

    Args:
        raw_output: Raw LLM response (SQL + optional CHART line).

    Returns:
        (sql_string, chart_spec_dict)
    """
    if "CHART:" in raw_output:
        parts = raw_output.split("CHART:", 1)
        sql = parts[0].strip()
        try:
            chart_spec = json.loads(parts[1].strip())
        except (json.JSONDecodeError, IndexError):
            chart_spec = {"type": "auto"}
    else:
        sql = raw_output.strip()
        chart_spec = {"type": "auto"}
    return sql, chart_spec


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

DETAIL_MARKERS = {"respondent_id", "resp_name", "device_id", "interviewer", "response_text"}

SKIP_COLS = {
    "respondent_id", "brand_id", "appliance_id", "date_id",
    "city_id", "zone_id", "id", "purchase_rank",
}

# Standard color palette
COLORS = {
    "primary":    "#4A90D9",
    "secondary":  "#7B61FF",
    "success":    "#2ecc71",
    "warning":    "#f39c12",
    "danger":     "#e74c3c",
    "info":       "#00BCD4",
    "palette":    ["#4A90D9", "#FF6B6B", "#2ecc71", "#f39c12", "#7B61FF",
                   "#00BCD4", "#FF9F43", "#A55EEA", "#26de81", "#FC5C65"],
}


def extract_key_metrics(df: pd.DataFrame) -> list[tuple[str, str]]:
    """Extract top 3-5 key metrics from the DataFrame."""
    mcols = metric_cols(df)[:5]
    results = []
    for c in mcols[:5]:
        if len(df) == 1:
            v = df.iloc[0][c]
        else:
            v = df[c].sum() if df[c].dtype in (int, float) else df[c].iloc[-1]
        if isinstance(v, float):
            results.append((c, f"{v:.1f}"))
        elif isinstance(v, int):
            results.append((c, f"{v:,}"))
        else:
            results.append((c, str(v)))
    return results[:5]


def has_col(df: pd.DataFrame, *frags: str) -> str | None:
    """Return the first column whose name contains any of the given fragments."""
    for col in df.columns:
        if any(f.lower() in col.lower() for f in frags):
            return col
    return None


def metric_cols(df: pd.DataFrame) -> list[str]:
    """Return all numeric columns that are likely metrics (not IDs)."""
    seen: set[str] = set()
    result: list[str] = []
    for c, dt in zip(df.columns, df.dtypes):
        if c in seen:
            continue
        seen.add(c)
        if (pd.api.types.is_numeric_dtype(dt)
                and c.lower() not in SKIP_COLS
                and not c.lower().endswith("_id")):
            result.append(c)
    return result


def string_cols(df: pd.DataFrame) -> list[str]:
    """Return all string/object/categorical columns."""
    seen: set[str] = set()
    result: list[str] = []
    for c, dt in zip(df.columns, df.dtypes):
        if c in seen:
            continue
        seen.add(c)
        if (dt == object
                or pd.api.types.is_string_dtype(dt)
                or isinstance(dt, pd.CategoricalDtype)):
            result.append(c)
    return result


def _col_label(col_name: str) -> str:
    """Convert column_name to 'Column Name' for display."""
    return col_name.replace("_", " ").title()


# ═══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL CHART RENDERERS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_metric_cards(df: pd.DataFrame, **_kw) -> None:
    """Single-row scalar results as metric cards."""
    cols_ui = st.columns(min(len(df.columns), 4))
    for i, col in enumerate(df.columns):
        v = df.iloc[0, i]
        with cols_ui[i % 4]:
            if isinstance(v, float):
                st.metric(_col_label(col), f"{v:.1f}")
            elif isinstance(v, int):
                st.metric(_col_label(col), f"{v:,}")
            else:
                st.metric(_col_label(col), str(v))


def _render_bar(df: pd.DataFrame, x: str | None = None, y: str | None = None,
                title: str | None = None, **_kw) -> None:
    """Horizontal bar chart — the default for category × metric data."""
    scols = string_cols(df)
    mcols = metric_cols(df)
    if not scols or not mcols:
        render_table(df)
        return

    x_col = x if x and x in df.columns else scols[0]
    y_col = y if y and y in df.columns else (
        has_col(df, "pct", "percent", "share")
        or has_col(df, "count", "n", "total", "mentions", "aware", "owners",
                   "female", "male", "raters")
        or mcols[0]
    )
    if not title:
        title = f"{_col_label(y_col)} by {_col_label(x_col)}"

    df_s = df.sort_values(y_col, ascending=True).tail(30)
    fmt = "%.1f" if df[y_col].dtype == float else "%d"
    fig = px.bar(
        df_s, x=y_col, y=x_col, orientation="h", text=y_col,
        color_discrete_sequence=[COLORS["primary"]],
        title=title,
    )
    fig.update_traces(texttemplate=f"%{{text:{fmt}}}", textposition="outside")
    fig.update_layout(
        height=max(350, len(df_s) * 32), showlegend=False,
        xaxis_title=_col_label(y_col), yaxis_title="",
        margin=dict(l=0, r=80, t=50, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Data table", expanded=False):
        render_table(df)


def _render_grouped_bar(df: pd.DataFrame, x: str | None = None,
                        y: str | None = None, color: str | None = None,
                        title: str | None = None, **_kw) -> None:
    """Side-by-side grouped bar chart for brand/entity comparisons."""
    scols = string_cols(df)
    mcols = metric_cols(df)
    if not scols or not mcols:
        render_table(df)
        return

    x_col = x if x and x in df.columns else scols[0]

    # If we have multiple metrics and no color grouping, melt for multi-metric view
    if len(mcols) >= 2 and not color:
        df_melted = df.melt(id_vars=[x_col], value_vars=mcols[:4],
                            var_name="Metric", value_name="Value")
        fig = px.bar(
            df_melted, x=x_col, y="Value", color="Metric",
            barmode="group", text="Value",
            color_discrete_sequence=COLORS["palette"],
            title=title or f"Comparison by {_col_label(x_col)}",
        )
    else:
        y_col = y if y and y in df.columns else mcols[0]
        color_col = color if color and color in df.columns else (
            scols[1] if len(scols) > 1 else None
        )
        fig = px.bar(
            df, x=x_col, y=y_col, color=color_col,
            barmode="group", text=y_col,
            color_discrete_sequence=COLORS["palette"],
            title=title or f"{_col_label(y_col)} by {_col_label(x_col)}",
        )

    fmt = "%.1f" if any(df[c].dtype == float for c in mcols) else "%d"
    fig.update_traces(texttemplate=f"%{{text:{fmt}}}", textposition="outside")
    fig.update_layout(
        height=max(400, len(df) * 40),
        margin=dict(l=0, r=80, t=50, b=30),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Data table", expanded=False):
        render_table(df)


def _render_stacked_bar(df: pd.DataFrame, x: str | None = None,
                        title: str | None = None, **_kw) -> None:
    """Stacked horizontal bar — useful for composition breakdowns."""
    scols = string_cols(df)
    mcols = metric_cols(df)
    if not scols or not mcols:
        render_table(df)
        return

    x_col = x if x and x in df.columns else scols[0]
    fig = go.Figure()
    for i, mc in enumerate(mcols[:5]):
        fig.add_bar(
            name=_col_label(mc), x=df[mc], y=df[x_col],
            orientation="h",
            marker_color=COLORS["palette"][i % len(COLORS["palette"])],
        )
    fig.update_layout(
        barmode="stack",
        title=title or f"Breakdown by {_col_label(x_col)}",
        height=max(350, len(df) * 35),
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=0, r=100, t=50, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Data table", expanded=False):
        render_table(df)


def _render_funnel(df: pd.DataFrame, x: str | None = None, y: str | None = None,
                   title: str | None = None, **_kw) -> None:
    """Funnel chart — TOM → SPONT → AIDED awareness progression."""
    scols = string_cols(df)
    mcols = metric_cols(df)
    if not scols or not mcols:
        render_table(df)
        return

    stage_col = x if x and x in df.columns else (has_col(df, "stage") or scols[0])
    value_col = y if y and y in df.columns else (
        has_col(df, "pct", "percent", "count") or mcols[0]
    )

    # Sort funnel stages in logical order if "stage" column detected
    stage_order = {"TOM": 0, "SPONT": 1, "AIDED": 2, "TOTAL": 3}
    if stage_col and has_col(df, "stage"):
        df = df.copy()
        df["_sort"] = df[stage_col].str.upper().map(stage_order).fillna(99)
        df = df.sort_values("_sort").drop(columns=["_sort"])

    fig = px.funnel(
        df, x=value_col, y=stage_col,
        color_discrete_sequence=COLORS["palette"],
        title=title or "Awareness Funnel",
    )
    fig.update_layout(
        height=max(300, len(df) * 80),
        margin=dict(l=0, r=80, t=50, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Data table", expanded=False):
        render_table(df)


def _render_pie(df: pd.DataFrame, x: str | None = None, y: str | None = None,
                title: str | None = None, **_kw) -> None:
    """Pie / donut chart for share/percentage distributions."""
    scols = string_cols(df)
    mcols = metric_cols(df)
    if not scols or not mcols:
        render_table(df)
        return

    name_col = x if x and x in df.columns else scols[0]
    value_col = y if y and y in df.columns else (
        has_col(df, "pct", "percent", "share", "count") or mcols[0]
    )

    fig = px.pie(
        df, names=name_col, values=value_col,
        color_discrete_sequence=COLORS["palette"],
        title=title or f"{_col_label(value_col)} Distribution",
        hole=0.35,  # donut style
    )
    fig.update_traces(textinfo="label+percent", textposition="outside")
    fig.update_layout(
        height=450,
        margin=dict(l=20, r=20, t=50, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Data table", expanded=False):
        render_table(df)


def _render_nps_waterfall(df: pd.DataFrame, title: str | None = None, **_kw) -> None:
    """NPS stacked horizontal bar — Detractors | Passives | Promoters."""
    p = has_col(df, "promoter")
    d = has_col(df, "detractor")
    pas = has_col(df, "passive")
    n_col = has_col(df, "brand_name", "brand")
    nps_c = has_col(df, " nps")

    if not (p and d and n_col):
        render_table(df)
        return

    rows = len(df)
    df_s = df.sort_values(nps_c if nps_c else p, ascending=True)
    fig = go.Figure()
    fig.add_bar(name="Detractors", x=df_s[d], y=df_s[n_col],
                orientation="h", marker_color=COLORS["danger"])
    if pas:
        fig.add_bar(name="Passives", x=df_s[pas], y=df_s[n_col],
                    orientation="h", marker_color=COLORS["warning"])
    fig.add_bar(name="Promoters", x=df_s[p], y=df_s[n_col],
                orientation="h", marker_color=COLORS["success"])
    fig.update_layout(
        barmode="stack", title=title or "NPS Breakdown",
        height=max(300, rows * 35),
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=0, r=100, t=50, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Data table", expanded=False):
        render_table(df)


def _render_line(df: pd.DataFrame, x: str | None = None, y: str | None = None,
                 color: str | None = None, title: str | None = None, **_kw) -> None:
    """Time-series line chart with markers."""
    mcols = metric_cols(df)
    time_col = x if x and x in df.columns else (
        has_col(df, "month_name", "month_num", "interview_month", "quarter")
    )
    y_col = y if y and y in df.columns else (
        has_col(df, "pct", "percent", "share")
        or has_col(df, "count", "n", "mentions", "aware", "owners")
        or (mcols[0] if mcols else None)
    )
    color_col = color if color and color in df.columns else (
        has_col(df, "brand_name", "brand", "appliance_name",
                "city_name", "zone_name", "gender")
    )
    if color_col == time_col:
        color_col = None

    if not time_col or not y_col:
        render_table(df)
        return

    fig = px.line(
        df, x=time_col, y=y_col, color=color_col, markers=True,
        color_discrete_sequence=COLORS["palette"],
        title=title or f"{_col_label(y_col)} over Time",
    )
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Data table", expanded=False):
        render_table(df)


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

def render_table(df: pd.DataFrame) -> None:
    """Formatted st.dataframe with smart column config."""
    cfg: dict[str, Any] = {}
    for col in df.columns:
        cl, lbl = col.lower(), _col_label(col)
        if any(x in cl for x in ["pct", "percent", "share", " nps", "avg", "mean"]):
            cfg[col] = st.column_config.NumberColumn(lbl, format="%.1f")
        elif any(x in cl for x in ["count", "_n", "total", "mentions", "owners",
                                     "aware", "female", "male", "raters"]):
            cfg[col] = st.column_config.NumberColumn(lbl, format="%d")
        elif any(x in cl for x in ["score", "rank"]):
            cfg[col] = st.column_config.NumberColumn(lbl, format="%.1f")
    st.dataframe(df, use_container_width=True, column_config=cfg, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CHART TYPE REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

_CHART_REGISTRY: dict[str, Any] = {
    "bar":           _render_bar,
    "stacked_bar":   _render_stacked_bar,
    "grouped_bar":   _render_grouped_bar,
    "funnel":        _render_funnel,
    "pie":           _render_pie,
    "nps_waterfall": _render_nps_waterfall,
    "line":          _render_line,
    "metric_cards":  _render_metric_cards,
    "table":         render_table,
}


# ═══════════════════════════════════════════════════════════════════════════════
# HEURISTIC CHART SELECTION (fallback when chart_spec is "auto")
# ═══════════════════════════════════════════════════════════════════════════════

def _auto_select_chart(df: pd.DataFrame, question: str) -> str:
    """Pick the best chart type using column-name heuristics."""
    rows = len(df)
    mcols = metric_cols(df)
    scols = string_cols(df)
    q = question.lower()

    # Detect detail/row-level data (always table)
    if any(c in df.columns for c in DETAIL_MARKERS):
        return "table"

    # NPS waterfall (check BEFORE metric_cards — a single-row NPS is still a waterfall)
    if has_col(df, "promoter") and has_col(df, "detractor") and rows <= 40:
        return "nps_waterfall"

    # Single scalar
    if rows == 1 and len(df.columns) == 1:
        return "metric_cards"

    # Single-row with multiple columns
    if rows == 1 and len(df.columns) <= 8:
        return "metric_cards"

    # Funnel detection (stage column + funnel keywords)
    stage_col = has_col(df, "stage")
    if stage_col and any(w in q for w in ["funnel", "progression", "stages"]):
        return "funnel"

    # Time-series
    time_col = has_col(df, "month_name", "month_num", "interview_month", "quarter")
    if time_col and mcols and rows <= 50 and "interview_date" not in df.columns:
        return "line"

    # Multi-metric comparison (grouped bar)
    if scols and len(mcols) >= 2 and rows >= 2:
        if any(w in q for w in ["compare", "vs", "side by side", "versus"]):
            return "grouped_bar"

    # Pie for percentage distributions
    if any(w in q for w in ["distribution", "share", "proportion", "pie"]):
        if scols and mcols and 2 <= rows <= 10:
            return "pie"

    # Default: horizontal bar for category × metric
    if scols and mcols and (rows <= 30 or any(
        w in q for w in ["chart", "graph", "plot", "visual", "bar", "show me"]
    )):
        return "bar"

    return "table"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def render_result(
    df: pd.DataFrame,
    question: str,
    chart_spec: dict | None = None,
) -> None:
    """
    Render a query result using chart_spec (if provided) or heuristic fallback.

    This is the single entry point for all chart/table rendering.

    Args:
        df:         The query result DataFrame.
        question:   The original user question (for heuristic chart selection).
        chart_spec: Optional chart specification dict from the LLM.
                    Keys: type, x, y, color, title.
                    If None or type=="auto", uses heuristic selection.
    """
    if df is None or df.empty:
        st.info("Query returned no rows.")
        return

    # Render key metrics panel (if multi-row data with metrics)
    mcols = metric_cols(df)
    if len(df) > 1 and mcols:
        metrics = extract_key_metrics(df)
        if len(metrics) >= 2:
            cols = st.columns(min(len(metrics), 4))
            for i, (label, value) in enumerate(metrics[:4]):
                with cols[i]:
                    st.metric(_col_label(label), value)
            st.divider()

    # Determine chart type
    if chart_spec and chart_spec.get("type", "auto") != "auto":
        chart_type = chart_spec["type"]
    else:
        chart_type = _auto_select_chart(df, question)

    # Get renderer
    renderer = _CHART_REGISTRY.get(chart_type)
    if renderer is None:
        renderer = _CHART_REGISTRY.get(_auto_select_chart(df, question), render_table)

    # Build kwargs from chart_spec
    kwargs: dict[str, Any] = {}
    if chart_spec:
        for key in ("x", "y", "color", "title"):
            if key in chart_spec and chart_spec[key]:
                kwargs[key] = chart_spec[key]

    # Render
    try:
        renderer(df, **kwargs)
    except Exception as e:
        st.warning(f"Chart rendering failed ({e}). Falling back to table.")
        render_table(df)
