"""
OxData — Schema Explorer (Power BI style data model view)
No API calls on this page — 100% local, reads directly from SQLite DB.
Shows: Interactive ER diagram, table cards with live row counts, column details, context explanation.
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

BASE_DIR = Path(__file__).parent.parent

# Use db_loader to get database - downloads on each session if needed
from db_loader import get_db_path
DB_PATH = get_db_path()

if not DB_PATH or not DB_PATH.exists():
    st.error(f"Database not available. DB_PATH: {DB_PATH}")
    st.stop()

# ── live row counts from DB ────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_row_counts() -> dict:
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    tables = [
        "fact_respondents", "fact_brand_awareness", "fact_brand_nps",
        "fact_kitchen_ownership", "fact_recent_purchase",
        "fact_room_appliances", "fact_verbatims",
        "dim_brand", "dim_city", "dim_zone",
        "dim_kitchen_appliance", "dim_room_appliance", "dim_date",
    ]
    views = [
        "v_respondents", "v_brand_awareness", "v_brand_nps",
        "v_kitchen_ownership", "v_recent_purchase", "v_room_appliances",
    ]
    counts = {}
    for t in tables + views:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            counts[t] = cur.fetchone()[0]
        except Exception:
            counts[t] = "—"
    con.close()
    return counts

@st.cache_data(ttl=300)
def get_table_columns(table: str) -> pd.DataFrame:
    con = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query(f"PRAGMA table_info({table})", con)
    con.close()
    return df[["name", "type", "notnull", "pk"]].rename(
        columns={"name": "Column", "type": "Type", "notnull": "Not Null", "pk": "PK"}
    )

@st.cache_data(ttl=300)
def get_sample(table: str, n: int = 5) -> pd.DataFrame:
    con = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query(f"SELECT * FROM {table} LIMIT {n}", con)
    con.close()
    return df


COUNTS = get_row_counts()


# ── Interactive ER diagram (Cytoscape.js) ─────────────────────────────────────
# Each entry: (technical_id, human_label, color, description, x_px, y_px)
# Positions designed as star schema: core fact at centre, outer facts mid-ring,
# dimensions on the periphery.

_ER_NODES = [
    ("fact_respondents",       "Respondents",       "#2563EB", "Core respondent demographics & geography",         420, 185),
    ("dim_date",               "Date",              "#16A34A", "39 unique interview dates (Apr–Jun 2021)",          215,  55),
    ("dim_city",               "City",              "#16A34A", "18 Indian cities across 4 zones",                  645,  70),
    ("dim_zone",               "Zone",              "#16A34A", "North / South / West / East",                      130, 115),
    ("fact_brand_awareness",   "Brand Awareness",   "#7C3AED", "TOM / SPONT / AIDED brand recall events",          110, 285),
    ("fact_brand_nps",         "Brand NPS",         "#7C3AED", "NPS scores 0-10 per respondent x brand rated",     215, 400),
    ("fact_kitchen_ownership", "Kitchen Ownership", "#7C3AED", "Kitchen appliances owned (binary flags as rows)",  420, 445),
    ("fact_recent_purchase",   "Recent Purchase",   "#7C3AED", "Recent purchases (ranked 1 = most recent)",        625, 400),
    ("fact_room_appliances",   "Room Appliances",   "#7C3AED", "Room appliances owned (fans, AC, bulbs, etc.)",    720, 285),
    ("dim_brand",              "Brand",             "#16A34A", "56 brands (codes 1-55 + 99 = Don't Know)",          50, 415),
    ("dim_kitchen_appliance",  "Kitchen Appliance", "#16A34A", "14 kitchen appliance types",                       445, 540),
    ("dim_room_appliance",     "Room Appliance",    "#16A34A", "17 room appliance types",                          810, 410),
]

_ER_EDGES = [
    ("fact_respondents",       "dim_date"),
    ("fact_respondents",       "dim_city"),
    ("fact_respondents",       "dim_zone"),
    ("fact_brand_awareness",   "fact_respondents"),
    ("fact_brand_awareness",   "dim_brand"),
    ("fact_brand_nps",         "fact_respondents"),
    ("fact_brand_nps",         "dim_brand"),
    ("fact_kitchen_ownership", "fact_respondents"),
    ("fact_kitchen_ownership", "dim_kitchen_appliance"),
    ("fact_recent_purchase",   "fact_respondents"),
    ("fact_recent_purchase",   "dim_kitchen_appliance"),
    ("fact_room_appliances",   "fact_respondents"),
    ("fact_room_appliances",   "dim_room_appliance"),
]


def render_er_diagram(counts: dict) -> None:
    """Render a fully interactive Cytoscape.js ER diagram inside an HTML component.

    Features:
    - Drag individual nodes to rearrange
    - Scroll to zoom in/out
    - Click-drag on empty canvas to pan
    - Hover over any node for tooltip with technical name, description, row count
    - Connected edges highlight on hover
    """
    nodes_js = json.dumps([
        {
            "id":    nid,
            "human": human,
            "color": color,
            "desc":  desc,
            "x":     x,
            "y":     y,
            "rows":  f"{counts[nid]:,}" if isinstance(counts.get(nid), int) else "—",
        }
        for nid, human, color, desc, x, y in _ER_NODES
    ])

    edges_js = json.dumps([
        {"id": f"e{i}", "source": src, "target": dst}
        for i, (src, dst) in enumerate(_ER_EDGES)
    ])

    html = f"""<!DOCTYPE html>
<html>
<head>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: transparent; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
#cy {{
  width: 100%;
  height: 560px;
  background: #0F172A;
  border-radius: 8px;
  cursor: grab;
}}
#cy:active {{ cursor: grabbing; }}
#tooltip {{
  position: fixed;
  background: #1E293B;
  color: #E2E8F0;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.7;
  pointer-events: none;
  display: none;
  border: 1px solid #334155;
  max-width: 270px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6);
  z-index: 9999;
}}
#wrapper {{ position: relative; }}
#legend {{
  position: absolute;
  bottom: 14px;
  left: 14px;
  display: flex;
  gap: 18px;
  font-size: 11px;
  color: #94A3B8;
  background: rgba(15,23,42,0.88);
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid #1E293B;
  pointer-events: none;
}}
#legend span {{ display: flex; align-items: center; gap: 6px; }}
.dot {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; flex-shrink: 0; }}
#hint {{
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 10px;
  color: #64748B;
  background: rgba(15,23,42,0.88);
  padding: 4px 10px;
  border-radius: 4px;
  pointer-events: none;
}}
</style>
</head>
<body>
<div id="wrapper">
  <div id="cy"></div>
  <div id="legend">
    <span><span class="dot" style="background:#2563EB"></span>Core fact</span>
    <span><span class="dot" style="background:#7C3AED"></span>Fact table</span>
    <span><span class="dot" style="background:#16A34A"></span>Dimension</span>
  </div>
  <div id="hint">Drag nodes &nbsp;&middot;&nbsp; Scroll to zoom &nbsp;&middot;&nbsp; Drag canvas to pan</div>
</div>
<div id="tooltip"></div>

<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.26.0/dist/cytoscape.min.js"></script>
<script>
const nodesData = {nodes_js};
const edgesData = {edges_js};

const elements = [];

nodesData.forEach(n => {{
  elements.push({{
    data: {{
      id:         n.id,
      label:      n.human + '\\n' + n.id,
      humanLabel: n.human,
      techName:   n.id,
      color:      n.color,
      desc:       n.desc,
      rows:       n.rows,
    }},
    position: {{ x: n.x, y: n.y }},
  }});
}});

edgesData.forEach(e => {{
  elements.push({{ data: {{ id: e.id, source: e.source, target: e.target }} }});
}});

const cy = cytoscape({{
  container: document.getElementById('cy'),
  elements,
  layout: {{ name: 'preset' }},
  style: [
    {{
      selector: 'node',
      style: {{
        'background-color':   'data(color)',
        'label':              'data(label)',
        'color':              '#FFFFFF',
        'text-valign':        'center',
        'text-halign':        'center',
        'font-size':          '9.5px',
        'font-family':        'system-ui, sans-serif',
        'width':              '92px',
        'height':             '46px',
        'shape':              'round-rectangle',
        'text-wrap':          'wrap',
        'text-max-width':     '86px',
        'border-width':       1.5,
        'border-color':       'rgba(255,255,255,0.15)',
        'transition-property':'border-color, border-width, background-color',
        'transition-duration':'80ms',
      }},
    }},
    {{
      selector: '#fact_respondents',
      style: {{
        'width':        '104px',
        'height':       '50px',
        'font-size':    '10px',
        'border-width': 2.5,
        'border-color': 'rgba(255,255,255,0.3)',
        'font-weight':  'bold',
      }},
    }},
    {{
      selector: 'node.hover',
      style: {{
        'border-color': '#F59E0B',
        'border-width': 3,
      }},
    }},
    {{
      selector: 'node:selected',
      style: {{
        'border-color': '#F59E0B',
        'border-width': 3,
      }},
    }},
    {{
      selector: 'edge',
      style: {{
        'width':               1.5,
        'line-color':          '#334155',
        'curve-style':         'bezier',
        'target-arrow-shape':  'vee',
        'target-arrow-color':  '#475569',
        'arrow-scale':         0.85,
        'opacity':             0.6,
        'transition-property': 'opacity, line-color, width',
        'transition-duration': '80ms',
      }},
    }},
    {{
      selector: 'edge.highlighted',
      style: {{
        'line-color':          '#60A5FA',
        'target-arrow-color':  '#60A5FA',
        'opacity':             1,
        'width':               2.5,
      }},
    }},
  ],
  userZoomingEnabled:  true,
  userPanningEnabled:  true,
  autoungrabify:       false,
  minZoom:             0.25,
  maxZoom:             4,
  wheelSensitivity:    0.25,
}});

// ── Tooltip ───────────────────────────────────────────────────────────────────
const tooltip = document.getElementById('tooltip');

cy.on('mouseover', 'node', function(e) {{
  const d = e.target.data();
  tooltip.innerHTML =
    '<div style="font-weight:700;font-size:13px;margin-bottom:2px">' + d.humanLabel + '</div>' +
    '<div style="color:#94A3B8;font-size:10px;font-family:monospace;letter-spacing:0.3px;margin-bottom:6px">' + d.techName + '</div>' +
    '<div style="margin-bottom:6px;color:#CBD5E1">' + d.desc + '</div>' +
    '<div style="color:#60A5FA;font-weight:600">' + d.rows + ' rows</div>';
  tooltip.style.display = 'block';
  e.target.addClass('hover');
  e.target.connectedEdges().addClass('highlighted');
}});

cy.on('mouseout', 'node', function(e) {{
  tooltip.style.display = 'none';
  e.target.removeClass('hover');
  e.target.connectedEdges().removeClass('highlighted');
}});

document.getElementById('cy').addEventListener('mousemove', function(e) {{
  if (tooltip.style.display !== 'none') {{
    tooltip.style.left = (e.clientX + 18) + 'px';
    tooltip.style.top  = (e.clientY - 10) + 'px';
  }}
}});

document.getElementById('cy').addEventListener('mouseleave', function() {{
  tooltip.style.display = 'none';
}});
</script>
</body>
</html>"""

    components.html(html, height=580, scrolling=False)


# ── view cards data ────────────────────────────────────────────────────────────
VIEW_CARDS = [
    {
        "name": "v_respondents",
        "icon": "👤",
        "purpose": "One row per respondent with all demographics & geography resolved.",
        "key_cols": "respondent_id, gender, age, age_band, city_name, zone_name, interview_date",
        "use_for": "Filter by city, zone, gender, date. Base for all percentages.",
    },
    {
        "name": "v_brand_awareness",
        "icon": "📢",
        "purpose": "One row per respondent × brand × awareness stage.",
        "key_cols": "respondent_id, stage (TOM/SPONT/AIDED), rank, brand_name",
        "use_for": "Brand funnel analysis — TOM%, spontaneous%, total awareness%.",
    },
    {
        "name": "v_brand_nps",
        "icon": "⭐",
        "purpose": "One row per respondent × brand NPS rating.",
        "key_cols": "respondent_id, brand_name, nps_score (0-10), nps_category",
        "use_for": "NPS scores, promoter/detractor breakdowns, brand loyalty.",
    },
    {
        "name": "v_kitchen_ownership",
        "icon": "🍳",
        "purpose": "One row per respondent × kitchen appliance owned.",
        "key_cols": "respondent_id, appliance_name",
        "use_for": "Appliance penetration rates, ownership by demographic.",
    },
    {
        "name": "v_recent_purchase",
        "icon": "🛒",
        "purpose": "One row per respondent × recently purchased appliance (ranked).",
        "key_cols": "respondent_id, purchase_rank (1–3), appliance_name",
        "use_for": "Which appliances were bought most recently. Rank 1 = most recent.",
    },
    {
        "name": "v_room_appliances",
        "icon": "🏠",
        "purpose": "One row per respondent × room appliance owned.",
        "key_cols": "respondent_id, appliance_name",
        "use_for": "Fan/AC/bulb/geyser ownership rates by city or zone.",
    },
]

TABLE_CARDS = {
    "Fact Tables": {
        "color": "#7C3AED",
        "tables": [
            {"name": "fact_respondents",       "desc": "Core respondent row. All 6,631 interviews."},
            {"name": "fact_brand_awareness",   "desc": "TOM / SPONT / AIDED recall events."},
            {"name": "fact_brand_nps",         "desc": "Per-brand NPS ratings (sparse — only rated brands)."},
            {"name": "fact_kitchen_ownership", "desc": "Kitchen appliance binary flags expanded to rows."},
            {"name": "fact_recent_purchase",   "desc": "Recent purchase selections with rank order."},
            {"name": "fact_room_appliances",   "desc": "Room appliance binary flags expanded to rows."},
            {"name": "fact_verbatims",         "desc": "Open-ended text responses (bq2a, others)."},
        ]
    },
    "Dimension Tables": {
        "color": "#16A34A",
        "tables": [
            {"name": "dim_brand",             "desc": "56 brand codes → names"},
            {"name": "dim_city",              "desc": "18 cities → zone mapping"},
            {"name": "dim_zone",              "desc": "4 zones (North/South/West/East)"},
            {"name": "dim_kitchen_appliance", "desc": "14 kitchen appliance types"},
            {"name": "dim_room_appliance",    "desc": "17 room appliance types"},
            {"name": "dim_date",              "desc": "39 interview dates with year/month/quarter"},
        ]
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

st.title("Schema Explorer")
st.caption("Data model for Project 1 — OX Wave 1. No API calls on this page.")

# ── top stats bar ──────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Respondents",     f"{COUNTS.get('fact_respondents', 0):,}")
c2.metric("Brand events",    f"{COUNTS.get('fact_brand_awareness', 0):,}")
c3.metric("NPS ratings",     f"{COUNTS.get('fact_brand_nps', 0):,}")
c4.metric("Appliance rows",  f"{COUNTS.get('fact_kitchen_ownership', 0) + COUNTS.get('fact_room_appliances', 0):,}")
c5.metric("Views available", "6")

st.divider()

# ── tabs ───────────────────────────────────────────────────────────────────────
tab_er, tab_views, tab_tables, tab_context = st.tabs([
    "ER Diagram",
    "Views (query these)",
    "Raw Tables",
    "How Context Works",
])

# ── TAB 1: ER DIAGRAM ─────────────────────────────────────────────────────────
with tab_er:
    st.markdown("#### Entity Relationship Diagram — Star Schema")
    st.caption(
        "Drag any node to reposition it. Scroll to zoom. Drag the background to pan. "
        "Hover over a node for details and row count."
    )
    render_er_diagram(COUNTS)

    st.markdown("---")
    st.markdown(
        """
        **Reading the diagram:**
        - **Blue (centre):** `fact_respondents` — the hub every other fact joins to.
        - **Purple:** Fact tables — one row per event (a brand mention, an NPS rating, an appliance owned).
        - **Green:** Dimension tables — lookup tables for codes → labels (brand names, city names, etc.)
        - **Arrows:** Foreign key direction. All views pre-join these so the LLM never needs to write JOINs.
        """
    )

# ── TAB 2: VIEWS ──────────────────────────────────────────────────────────────
with tab_views:
    st.markdown("#### 6 Pre-joined Views — Always query these in the chat")
    st.info(
        "Views join all dimension labels into the fact data. When you chat, the LLM is told "
        "to query views only — this means it writes simpler SQL and is less likely to hallucinate column names.",
        icon="ℹ️",
    )

    for card in VIEW_CARDS:
        cnt = COUNTS.get(card["name"], "—")
        badge = f"{cnt:,} rows" if isinstance(cnt, int) else cnt
        with st.expander(f"{card['icon']}  **{card['name']}** — {badge}", expanded=False):
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.markdown(f"**Purpose:** {card['purpose']}")
                st.markdown(f"**Key columns:** `{card['key_cols']}`")
                st.markdown(f"**Use for:** {card['use_for']}")
            with col_r:
                st.markdown("**Column list:**")
                try:
                    cols_df = get_table_columns(card["name"])
                    st.dataframe(cols_df, use_container_width=True, hide_index=True, height=220)
                except Exception:
                    st.caption("(Run ETL to populate DB)")

            st.markdown("**Sample rows:**")
            try:
                sample = get_sample(card["name"], 3)
                st.dataframe(sample, use_container_width=True, hide_index=True)
            except Exception:
                st.caption("(No data yet)")

# ── TAB 3: RAW TABLES ─────────────────────────────────────────────────────────
with tab_tables:
    st.markdown("#### Raw Tables — For reference only (chat queries the views)")

    for category, info in TABLE_CARDS.items():
        st.markdown(f"##### {category}")
        col_groups = st.columns(3)
        for i, table in enumerate(info["tables"]):
            cnt = COUNTS.get(table["name"], "—")
            badge = f"{cnt:,}" if isinstance(cnt, int) else cnt
            with col_groups[i % 3]:
                with st.container(border=True):
                    st.markdown(
                        f"**{table['name']}**  \n"
                        f"<span style='color:#94A3B8;font-size:12px'>{badge} rows</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(table["desc"])
                    with st.expander("Columns", expanded=False):
                        try:
                            cols_df = get_table_columns(table["name"])
                            st.dataframe(
                                cols_df[["Column", "Type", "PK"]],
                                use_container_width=True, hide_index=True, height=180,
                            )
                        except Exception:
                            st.caption("—")
        st.markdown("")

# ── TAB 4: HOW CONTEXT WORKS ──────────────────────────────────────────────────
with tab_context:
    st.markdown("#### How the LLM Understands the Database")

    st.markdown(
        "When you type a question in the chat, here is exactly what gets sent to the Groq API:"
    )

    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown("##### 1. System Prompt (skill-specific, 350–900 tokens)")
        st.code(
            """[system]
You are a SQL analyst for a SQLite survey database.

=== RULES ===
1. Return ONLY raw SQL. No fences. No comments.
2. Query VIEWS only (never raw fact_ tables).
3. Penetration %: ROUND(count*100.0 /
   (SELECT COUNT(*) FROM fact_respondents), 1)
4. Always include count + pct columns.
5. Carry forward prior filters on follow-up.
6. Never invent column names.

=== VIEW: v_brand_nps  (10,200 rows) ===
  respondent_id, brand_name
  nps_score (0-10), nps_category
  + gender, age, city_name, zone_name, ...

NPS = ROUND((%promoters - %detractors)*100, 1)
Use HAVING COUNT(*) >= 50 to filter sparse brands.

=== EXAMPLES ===
-- NPS by brand
SELECT brand_name, COUNT(*) raters,
  ROUND((SUM(CASE WHEN nps_score>=9 THEN 1.0 ELSE 0 END)
       - SUM(CASE WHEN nps_score<=6 THEN 1.0 ELSE 0 END))
    * 100.0 / COUNT(*), 1) nps
FROM v_brand_nps
GROUP BY brand_name HAVING COUNT(*) >= 50
ORDER BY nps DESC;
""",
            language="text",
        )

    with c_right:
        st.markdown("##### 2. Prior Conversation (last 4 turns, Q+SQL only)")
        st.code(
            """[user]   How many respondents are from Patna?
[asst]   SELECT city_name, COUNT(*) ...
         WHERE city_name = 'Patna'

[user]   Tell me their details
         ^ "their" resolved because prior SQL
           had WHERE city_name = 'Patna'.
           LLM carries this filter forward.
""",
            language="text",
        )

        st.markdown("##### 3. Your question")
        st.code("[user]   Tell me their details", language="text")

        st.markdown("##### Token budget per call (with Skill Foundry)")
        st.dataframe(
            pd.DataFrame([
                ["Skill system prompt",           "350–900",   "Varies by skill routed to"],
                ["Prior turns (Q+SQL, 4 turns)",  "~400 max",  "Grows with conversation"],
                ["Your question",                 "~15",       "Variable"],
                ["Total input",                   "~800–1,300","Was 6,500 before BUG-008"],
                ["SQL output",                    "~80",       "Short — SQL is concise"],
            ], columns=["Component", "Tokens (est.)", "Notes"]),
            hide_index=True, use_container_width=True,
        )

    st.divider()
    st.markdown(
        """
        ##### How the Skill Foundry reduces tokens

        Instead of loading the full schema for every question, the router classifies your
        question by keyword (zero API calls) and only injects the relevant skill's schema slice.

        | Skill routed | Schema loaded | Est. tokens |
        |---|---|---|
        | NPS / Brand Ratings | `v_brand_nps` only | ~500 |
        | Brand Awareness | `v_brand_awareness` only | ~550 |
        | Kitchen Ownership | `v_kitchen_ownership` only | ~380 |
        | Room Appliances | `v_room_appliances` only | ~380 |
        | Recent Purchases | `v_recent_purchase` only | ~400 |
        | Respondents | `v_respondents` only | ~450 |
        | General (fallback) | Overview of all 6 views | ~900 |

        ##### Why pre-joined views matter for the LLM

        Without views, the LLM would need to write:
        ```sql
        SELECT db.brand_name, COUNT(*) FROM fact_brand_awareness fba
        JOIN dim_brand db ON fba.brand_id = db.brand_id
        JOIN fact_respondents fr ON fba.respondent_id = fr.respondent_id
        JOIN dim_city dc ON fr.city_id = dc.city_id
        WHERE dc.city_name = 'Mumbai'
        GROUP BY db.brand_name
        ```

        With views, it just writes:
        ```sql
        SELECT brand_name, COUNT(*) FROM v_brand_awareness
        WHERE city_name = 'Mumbai' GROUP BY brand_name
        ```

        Simpler SQL = fewer hallucinations, fewer tokens in the system prompt
        (no need to explain all the join keys).
        """
    )
