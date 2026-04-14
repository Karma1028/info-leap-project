"""
Capability: nps
===============
Net Promoter Score analysis.
NPS is an industry-standard loyalty metric: (Promoters% - Detractors%) × 100.

This logic applies to any project where respondents rate entities on a 0-10 scale.
Common in consumer surveys, healthcare (patient experience), B2B (vendor satisfaction).

Required binding keys (from config/project_N.CAPABILITIES["nps"]):
  view               — pre-joined NPS view name
  view_rows          — approximate row count (display only)
  entity_col         — column for entity name (e.g., brand_name, doctor_name)
  score_col          — column for the 0-10 score (e.g., nps_score)
  category_col       — column for pre-computed category label (Promoter/Passive/Detractor)
  promoter_min       — minimum score to be a promoter (typically 9)
  passive_min        — minimum score for passive (typically 7)
  passive_max        — maximum score for passive (typically 8)
  detractor_max      — maximum score to be a detractor (typically 6)
  min_raters         — minimum raters required for a valid NPS (typically 50)
  sparse_note        — plain-English note about sparsity of ratings
"""

CAPABILITY_ID = "nps"
DESCRIPTION   = "Net Promoter Score — promoter/passive/detractor analysis"

KEY_COLUMNS_SUMMARY = (
    "respondent_id, {entity_col}, {score_col} (0-10), {category_col}"
)


def format_prompt(binding: dict, shared_cols: str, respondent_table: str) -> str:
    b = binding
    return f"""
=== VIEW: {b['view']}  ({b['view_rows']} rows) ===
  respondent_id
  {b['entity_col']}
  {b['score_col']}  — integer 0 to 10
  {b['category_col']} — 'Promoter' ({b['promoter_min']}-10) | 'Passive' ({b['passive_min']}-{b['passive_max']}) | 'Detractor' (0-{b['detractor_max']})
{shared_cols}

IMPORTANT: Output ONLY a single SQL query. Do NOT provide multiple queries or explanations.

NOTE: {b['sparse_note']}

=== NPS FORMULA ===
Use HAVING COUNT(*) >= {b['min_raters']} to exclude entities with too few raters.

ROUND(
  (SUM(CASE WHEN {b['score_col']} >= {b['promoter_min']} THEN 1.0 ELSE 0 END)
 - SUM(CASE WHEN {b['score_col']} <= {b['detractor_max']} THEN 1.0 ELSE 0 END))
  * 100.0 / COUNT(*), 1) AS nps

=== EXAMPLE ===
-- Full NPS waterfall per entity
SELECT {b['entity_col']},
  COUNT(*) total,
  SUM(CASE WHEN {b['score_col']} >= {b['promoter_min']} THEN 1 ELSE 0 END) promoters,
  SUM(CASE WHEN {b['score_col']} BETWEEN {b['passive_min']} AND {b['passive_max']} THEN 1 ELSE 0 END) passives,
  SUM(CASE WHEN {b['score_col']} <= {b['detractor_max']} THEN 1 ELSE 0 END) detractors,
  ROUND(
    (SUM(CASE WHEN {b['score_col']} >= {b['promoter_min']} THEN 1.0 ELSE 0 END)
   - SUM(CASE WHEN {b['score_col']} <= {b['detractor_max']} THEN 1.0 ELSE 0 END))
    * 100.0 / COUNT(*), 1) AS nps
FROM {b['view']}
GROUP BY {b['entity_col']}
HAVING COUNT(*) >= {b['min_raters']}
ORDER BY nps DESC;
"""
