"""
Capability: awareness
=====================
Brand / product awareness funnel.
Covers top-of-mind (TOM), spontaneous (SPONT), and aided recall (AIDED).

This logic is industry-standard for consumer brand tracking studies.
It works for any project where respondents are asked to recall brands
in sequence — unprompted first, then from a shown list.

Layer 2: Contains the business logic and SQL patterns.
Layer 3 (config/project_N.py) provides: view name, column names, stage labels.

Required binding keys (all supplied from config/project_N.CAPABILITIES["awareness"]):
  view           — name of the pre-joined awareness view
  view_rows      — approximate row count (display only)
  entity_col     — column holding the entity name (e.g., brand_name, product_name)
  stage_col      — column holding the recall stage value
  tom_value      — value for top-of-mind stage  (e.g., 'TOM')
  spont_value    — value for spontaneous stage   (e.g., 'SPONT')
  aided_value    — value for aided stage         (e.g., 'AIDED')
  exclude_filter — SQL fragment to filter invalid entities (e.g., "brand_name != 'Don''t Know / None'")
  tom_desc       — plain-English description of the TOM stage
  spont_desc     — plain-English description of the SPONT stage
  aided_desc     — plain-English description of the AIDED stage
"""

CAPABILITY_ID = "awareness"
DESCRIPTION   = "Brand/product awareness funnel — TOM, spontaneous, aided recall"

# One-liner summary used when building the GENERAL skill's views section
KEY_COLUMNS_SUMMARY = (
    "respondent_id, {stage_col} ('{tom_value}'|'{spont_value}'|'{aided_value}'), "
    "rank, {entity_col}"
)


def format_prompt(binding: dict, shared_cols: str, respondent_table: str) -> str:
    """
    Assemble the awareness skill prompt section.

    Args:
        binding:          Layer 3 dict from config/project_N.CAPABILITIES["awareness"]
        shared_cols:      Common demographic/geo columns shared across all views in this project
        respondent_table: Table name used for penetration % denominator
    """
    b = binding  # shorthand
    return f"""
=== VIEW: {b['view']}  ({b['view_rows']} rows) ===
  respondent_id
  {b['stage_col']} — '{b['tom_value']}' | '{b['spont_value']}' | '{b['aided_value']}'
  rank (integer; NULL for {b['aided_value']})
  {b['entity_col']}
{shared_cols}

IMPORTANT: Output ONLY a single SQL query. Do NOT provide multiple queries or explanations.

=== STAGE LOGIC ===
- {b['tom_value']}   = {b['tom_desc']}
- {b['spont_value']}  = {b['spont_desc']}
- {b['aided_value']} = {b['aided_desc']}
- Always filter invalid entities: WHERE {b['exclude_filter']}

SPONTANEOUS AWARENESS  = {b['stage_col']} IN ('{b['tom_value']}', '{b['spont_value']}')
  → COUNT(DISTINCT respondent_id)

TOTAL AWARENESS (aided) = all 3 stages
  → COUNT(DISTINCT respondent_id)

=== EXAMPLES ===
-- TOM brand share
SELECT {b['entity_col']}, COUNT(*) mentions,
  ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM {respondent_table}), 1) pct
FROM {b['view']}
WHERE {b['stage_col']} = '{b['tom_value']}' AND {b['exclude_filter']}
GROUP BY {b['entity_col']} ORDER BY mentions DESC;

-- Full awareness funnel (TOM + Spont + Total per entity)
SELECT {b['entity_col']},
  SUM(CASE WHEN {b['stage_col']} = '{b['tom_value']}' THEN 1 ELSE 0 END) tom,
  ROUND(SUM(CASE WHEN {b['stage_col']} = '{b['tom_value']}' THEN 1 ELSE 0 END) * 100.0
    / (SELECT COUNT(*) FROM {respondent_table}), 1) tom_pct,
  COUNT(DISTINCT CASE WHEN {b['stage_col']} IN ('{b['tom_value']}', '{b['spont_value']}')
    THEN respondent_id END) spont_aware,
  ROUND(COUNT(DISTINCT CASE WHEN {b['stage_col']} IN ('{b['tom_value']}', '{b['spont_value']}')
    THEN respondent_id END) * 100.0 / (SELECT COUNT(*) FROM {respondent_table}), 1) spont_pct,
  COUNT(DISTINCT respondent_id) total_aware,
  ROUND(COUNT(DISTINCT respondent_id) * 100.0
    / (SELECT COUNT(*) FROM {respondent_table}), 1) total_pct
FROM {b['view']} WHERE {b['exclude_filter']}
GROUP BY {b['entity_col']} ORDER BY tom DESC;

=== CROSS-SKILL: DEMOGRAPHIC BREAKDOWN OF AWARE RESPONDENTS ===
For "brand awareness by gender/age/city" queries:

-- Awareness by gender (single brand)
SELECT gender, COUNT(DISTINCT respondent_id) aware,
  ROUND(COUNT(DISTINCT respondent_id) * 100.0 / (SELECT COUNT(*) FROM {respondent_table}), 1) pct
FROM {b['view']}
WHERE brand_name = 'Crompton' AND {b['stage_col']} IN ('{b['tom_value']}', '{b['spont_value']}') AND {b['exclude_filter']}
GROUP BY gender;

-- Awareness by age band (single brand)
SELECT age_band, COUNT(DISTINCT respondent_id) aware,
  ROUND(COUNT(DISTINCT respondent_id) * 100.0 / (SELECT COUNT(*) FROM {respondent_table}), 1) pct
FROM {b['view']}
WHERE brand_name = 'Crompton' AND {b['stage_col']} IN ('{b['tom_value']}', '{b['spont_value']}') AND {b['exclude_filter']}
GROUP BY age_band;

-- Awareness by city (single brand, top 10)
SELECT city_name, COUNT(DISTINCT respondent_id) aware,
  ROUND(COUNT(DISTINCT respondent_id) * 100.0 / (SELECT COUNT(*) FROM {respondent_table}), 1) pct
FROM {b['view']}
WHERE brand_name = 'Crompton' AND {b['stage_col']} IN ('{b['tom_value']}', '{b['spont_value']}') AND {b['exclude_filter']}
GROUP BY city_name ORDER BY aware DESC LIMIT 10;
"""
