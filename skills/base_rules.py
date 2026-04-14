"""
Layer 1 — Universal Rules
=========================
These rules are prepended to EVERY skill prompt regardless of project or capability.
They never change unless the SQL generation approach itself changes.

Design principle: Rules that are true for ALL projects, ALL capabilities.
If a rule only applies to one project or one view, it belongs in Layer 3 (config/project_N.py).
"""

_TEMPLATE = """\
=== RULES (apply always) ===
1. Return ONLY raw SQL. No markdown fences. No comments. No pre-computed results.
2. Query VIEWS only — never raw fact_ tables (fact_respondents, fact_brand_awareness, etc.).
3. Penetration %: ROUND(count * 100.0 / (SELECT COUNT(*) FROM {respondent_table}), 1)
4. Include both count AND pct columns when share / percentage is asked.
5. Follow-up pronouns ("their", "those", "that brand") → apply the same WHERE filter as the prior query.
6. Never invent column names or values. Use ONLY the exact column names and values from the DATA DICTIONARY below.
7. String matching is CASE-SENSITIVE. Use exact values from the dictionary.
8. After the SQL, on a NEW LINE starting with CHART:, return a JSON chart spec:
   CHART: {{"type": "bar|grouped_bar|stacked_bar|funnel|pie|nps_waterfall|line|table|metric_cards", "x": "col", "y": "col", "color": "col_or_null", "title": "short title"}}
   If no chart fits, return CHART: {{"type": "table"}}
"""


def get_rules(respondent_table: str = "fact_respondents") -> str:
    """
    Return the universal rules block with the correct respondent table name.

    Args:
        respondent_table: The table used as denominator for penetration percentages.
                          Always 'fact_respondents' for Project 1, but could differ
                          in future projects (e.g., 'fact_patients' for a healthcare study).
    """
    return _TEMPLATE.format(respondent_table=respondent_table)
