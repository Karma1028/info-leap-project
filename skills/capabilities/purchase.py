"""
Capability: purchase
====================
Ranked / recency purchase behaviour.
Covers scenarios where respondents select multiple items in order of recency or preference.

Key distinction from ownership: RANK matters here.
Rank 1 = most recently purchased / primary choice.

Required binding keys (from config/project_N.CAPABILITIES["purchase"]):
  view         — pre-joined purchase view
  view_rows    — approximate row count
  entity_col   — column for entity name
  rank_col     — column for purchase rank (integer, 1 = most recent)
  max_rank     — maximum rank value (e.g., 3 = respondents pick up to 3 items)
  rank_desc    — plain-English description of the rank meaning
  entity_list  — comma-separated list of valid entity names
"""

CAPABILITY_ID = "purchase"
DESCRIPTION   = "Ranked purchase behaviour — recency and primary/secondary choices"

KEY_COLUMNS_SUMMARY = "respondent_id, {rank_col} (1-{max_rank}), {entity_col}"


def format_prompt(binding: dict, shared_cols: str, respondent_table: str) -> str:
    b = binding
    return f"""
=== VIEW: {b['view']}  ({b['view_rows']} rows) ===
  respondent_id
  {b['rank_col']}  — {b['rank_desc']}
  {b['entity_col']}
{shared_cols}

IMPORTANT: Output ONLY a single SQL query. Do NOT provide multiple queries or explanations.

NOTE: {b['rank_col']} goes from 1 to {b['max_rank']}.
Rank 1 = most recently purchased / primary selection.
Use WHERE {b['rank_col']} = 1 for "most recently purchased" analysis.
Use no rank filter to include all purchases regardless of recency.

VALID ENTITY NAMES: {b['entity_list']}

=== EXAMPLES ===
-- Most recently purchased entity (rank 1 only)
SELECT {b['entity_col']}, COUNT(*) n,
  ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM {respondent_table}), 1) pct
FROM {b['view']}
WHERE {b['rank_col']} = 1
GROUP BY {b['entity_col']} ORDER BY n DESC;

-- All purchases regardless of rank
SELECT {b['entity_col']}, COUNT(*) total_purchases
FROM {b['view']}
GROUP BY {b['entity_col']} ORDER BY total_purchases DESC;

-- Purchase rank distribution for one entity
SELECT {b['rank_col']}, COUNT(*) n
FROM {b['view']}
WHERE {b['entity_col']} = 'Mixer Grinder / Mixie'
GROUP BY {b['rank_col']} ORDER BY {b['rank_col']};
"""
