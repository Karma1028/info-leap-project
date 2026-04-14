# Business Logic & Data Rules

## Brand Awareness Funnel (bq1a → bq1b → bq1c)

The funnel has three stages, each stored as a separate `stage` value in `fact_brand_awareness`:

| Stage | Code | Question | Type | Order matters? |
|-------|------|----------|------|----------------|
| TOM | bq1a | "Which brand comes to mind first?" | Single-select | N/A (always rank 1) |
| SPONT | bq1b | "Which other brands do you remember?" | Multi-select, NO screen shown | YES — first mentioned = strongest recall |
| AIDED | bq1c | "Which of these brands have you heard of?" | Multi-select, screen shown | NO — tick all that apply |

**rank column:**
- TOM: always 1
- SPONT: 1 = first mentioned (after TOM), 2 = second, etc. This is the spontaneous recall rank.
- AIDED: NULL — screen-selection has no meaningful order

**Funnel logic for analysis:**
- TOM% = respondents who mentioned brand in TOM / total respondents
- Spontaneous awareness% = respondents who mentioned brand in TOM OR SPONT / total respondents
- Total awareness (aided)% = respondents who mentioned brand in TOM OR SPONT OR AIDED / total respondents

```sql
-- Correct spontaneous awareness (TOM + SPONT, deduplicated per respondent)
SELECT brand_name,
       COUNT(DISTINCT respondent_id) AS spont_aware,
       ROUND(COUNT(DISTINCT respondent_id)*100.0 /
             (SELECT COUNT(*) FROM fact_respondents), 1) AS pct
FROM v_brand_awareness
WHERE stage IN ('TOM','SPONT')
GROUP BY brand_name ORDER BY spont_aware DESC;
```

---

## NPS Calculation (bq2b)

**Source:** Columns `bq2b_1` through `bq2b_53` in source Excel.  
`bq2b_N` = NPS score (0-10) that the respondent gave to brand N.  
Only filled for brands the respondent has used/owned — most respondents have 1-3 brands rated.

**NPS Score → Category:**
- 9-10 → Promoter
- 7-8  → Passive  
- 0-6  → Detractor

**Net Promoter Score formula:**
```sql
SELECT brand_name,
       COUNT(*) total,
       SUM(CASE WHEN nps_score >= 9 THEN 1 ELSE 0 END) promoters,
       SUM(CASE WHEN nps_score <= 6 THEN 1 ELSE 0 END) detractors,
       ROUND((SUM(CASE WHEN nps_score >= 9 THEN 1.0 ELSE 0 END) -
              SUM(CASE WHEN nps_score <= 6 THEN 1.0 ELSE 0 END)) /
             COUNT(*) * 100, 1) AS nps
FROM v_brand_nps
GROUP BY brand_name HAVING total >= 50
ORDER BY nps DESC;
```

---

## Recent Purchase Ranking (mq3b)

**Question:** "Which are the 3 appliances you have purchased recently?" (RANKED)  
**Max selections:** 3  
**`purchase_rank`:** 1 = most recently purchased / primary purchase, 2 and 3 = secondary

**Source parsing — important:**  
The survey tool sometimes concatenated codes as a single number (e.g., `40810` = appliances 4, 8, 10 in ranked order). The ETL handles this by:
1. If the string has spaces or commas → split normally
2. If it's a pure-digit string longer than 2 chars → pad to even length, split into 2-char pairs

This is specific to the survey platform used in Wave 1. Future projects may not have this issue.

---

## Kitchen Appliance Ownership (mq3a)

**Question:** "Which of these kitchen appliances do you own?" (Multi-select)  
**Source:** Binary flag columns `mq3a/1` through `mq3a/15` (1=owns, 0=doesn't own)  
**Note:** Code 15 is blank/null in the datamap — treated as invalid and excluded.

---

## Room Appliance Ownership (mq2a)

**Question:** Asked per room in the home — which electrical equipment in each room?  
**Source:** Binary flag columns `mq2a/1` through `mq2a/18`  
**Note:** Code 10 is intentionally absent in the source codebook (gap in sequence).

The DB stores one row per respondent × appliance code — it does NOT preserve which room the appliance was in (room-level data not in the export).

---

## Geography

**Centres (cities):** 18 cities coded 1-18. Mapped in `config/project_1.py`.  
**Zones:** 4 zones (North/South/West/East). Each city belongs to one zone.

City → Zone mapping:
- **North:** Delhi, Lucknow, Bikaner, Patiala
- **South:** Chennai, Cochin, Guntur, Hassan, Hyderabad, Bangalore
- **West:** Mumbai, Ahmedabad, Kolhapur, Ujjain
- **East:** Kolkata, Patna, Bhubaneshwar, Nagaon

---

## Demographics

**Gender:** s1 column — 1=Male, 2=Female  
**Age:** Exact age in `age` column. Banded in `age_band`: '25-35' or '36-50'  
**SEC class:** NOT in export. Was NCCS A-E derived from s4a (education) × s4b (durables owned). Must be added from a separate source.

---

## Date Handling

**Source column:** `int_stime` (interview start date, Excel datetime object or DD-MM-YYYY string)  
**Date range:** 2021-04-06 to 2021-06-09 (39 unique dates)  
**Year/Month added:** `dim_date` has year, month_num, month_name, quarter, day_of_week  
**Time of day:** Available in `int_stime.1` column (not loaded — add if needed)

---

## Missing / Null Data

| Column | Status | Notes |
|--------|--------|-------|
| `category` | NULL everywhere | mq6 (quota assignment) not in export |
| `sec` | Not loaded | NCCS class not in export |
| `bq2b` (parent) | Entirely null in source | Only sub-columns bq2b_1..53 have data |
| `intro`, `intro3` | Entirely null in source | Dropped |
| mq3a code 15 | Blank in datamap | Not loaded |
| mq2a code 10 | Gap in source codebook | Not loaded |

---

## Brand Code Quirks

- Code **99** = "Don't Know / None" — appears in bq1a and bq1c. Loaded into dim_brand and fact tables. Filter out for brand analysis: `WHERE brand_name != 'Don''t Know / None'`
- Codes **54** and **55** = "Others (Specify 1/2)" — piped verbatim values. If the respondent wrote a brand name, it appears in `mq1a_others` / `mq1b_others` columns (stored in fact_verbatims).

---

## Counting Rules for Percentages

**Always use `fact_respondents` as the denominator for penetration %:**
```sql
-- CORRECT: % of all respondents who own Mixer Grinder
SELECT ROUND(COUNT(DISTINCT ko.respondent_id)*100.0 /
             (SELECT COUNT(*) FROM fact_respondents), 1)
FROM fact_kitchen_ownership ko
JOIN dim_kitchen_appliance a ON ko.appliance_id = a.appliance_id
WHERE a.appliance_name = 'Mixer Grinder / Mixie';
```

**For brand metrics, use the base relevant to the question:**
- TOM%  = brand TOM count / total respondents
- NPS average = AVG(nps_score) for that brand
- Awareness% = distinct respondents who mentioned brand / total respondents
