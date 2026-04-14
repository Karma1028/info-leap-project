"""
Capability: ownership
=====================
Binary ownership / penetration analysis.
Covers appliances, products, or any category where respondents tick all that apply.

The source data is binary flag columns expanded into one row per respondent × entity.
Penetration % = distinct owners / total respondents.

Required binding keys (from config/project_N.CAPABILITIES["ownership"]):
  view         — pre-joined ownership view
  view_rows    — approximate row count
  entity_col   — column for entity name (e.g., appliance_name)
  entity_list  — comma-separated list of valid entity names (for reference)
"""

CAPABILITY_ID = "ownership"
DESCRIPTION   = "Ownership / penetration analysis (binary — owns or doesn't own)"

KEY_COLUMNS_SUMMARY = "respondent_id, {entity_col}"


def format_prompt(binding: dict, shared_cols: str, respondent_table: str) -> str:
    b = binding
    return f"""
=== VIEW: {b['view']}  ({b['view_rows']} rows) ===
  respondent_id
  {b['entity_col']}
{shared_cols}

IMPORTANT: Output ONLY a single SQL query. Do NOT provide multiple queries or explanations.

VALID ENTITY NAMES: {b['entity_list']}

NOTE: One row per respondent per entity owned. Use COUNT(DISTINCT respondent_id)
for headcount. Do NOT use COUNT(*) for penetration (double-counts respondents
who own multiple items — but here each row is a unique respondent-entity pair,
so COUNT(*) = COUNT(DISTINCT respondent_id) for a single entity filter).

=== EXAMPLES ===
-- Penetration rate for all entities
SELECT {b['entity_col']},
  COUNT(DISTINCT respondent_id) owners,
  ROUND(COUNT(DISTINCT respondent_id) * 100.0
    / (SELECT COUNT(*) FROM {respondent_table}), 1) pct
FROM {b['view']}
GROUP BY {b['entity_col']} ORDER BY owners DESC;

-- Ownership rate for a specific entity by zone
SELECT zone_name,
  COUNT(DISTINCT respondent_id) owners,
  ROUND(COUNT(DISTINCT respondent_id) * 100.0
    / (SELECT COUNT(*) FROM {respondent_table}), 1) pct
FROM {b['view']}
WHERE {b['entity_col']} = 'Mixer Grinder / Mixie'
GROUP BY zone_name ORDER BY owners DESC;
"""
