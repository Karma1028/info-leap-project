# Database Schema — oxdata.db

Location: `data/{project_id}/oxdata.db`  
Engine: SQLite  
Pattern: Star Schema (dimension + fact tables + pre-joined views)

---

## ALWAYS QUERY THE VIEWS, NOT THE RAW TABLES

The views (`v_*`) have all dimension labels already joined in.  
Use `brand_name`, `city_name`, `appliance_name` directly — no manual joins needed.

---

## VIEWS (use these)

### v_respondents
One row per respondent. All demographic + geographic labels resolved.

| Column | Type | Description |
|--------|------|-------------|
| respondent_id | INT | Unique respondent identifier (1-based row number) |
| resp_name | TEXT | Respondent name |
| gender | TEXT | 'Male' or 'Female' |
| age | INT | Exact age |
| age_band | TEXT | '25-35' or '36-50' |
| interviewer | TEXT | Interviewer name |
| category | TEXT | Product category (NULL — mq6 not in source data) |
| city_name | TEXT | City name (e.g. 'Delhi', 'Mumbai') |
| zone_name | TEXT | Zone (North / South / West / East) |
| interview_date | TEXT | ISO date YYYY-MM-DD |
| interview_year | INT | 2021 |
| interview_month | INT | Month number 1-12 |
| interview_month_name | TEXT | 'April', 'May', etc. |
| interview_quarter | INT | 1-4 |

### v_brand_awareness
One row per respondent × brand × stage. Use for TOM, spontaneous, aided recall analysis.

| Column | Type | Description |
|--------|------|-------------|
| respondent_id | INT | |
| stage | TEXT | 'TOM' (top of mind) \| 'SPONT' (spontaneous) \| 'AIDED' (aided recall) |
| rank | INT | 1=first mentioned. NULL for AIDED (no inherent order on screen). |
| brand_id | INT | |
| brand_name | TEXT | Brand name (e.g. 'Crompton', 'Bajaj') |
| gender, age, age_band | | From respondent |
| city_name, zone_name | | From respondent |
| interview_date, interview_year, interview_month, interview_month_name, interview_quarter | | |

**Stage logic:**
- `TOM`: Single brand first mentioned spontaneously (bq1a). Every respondent has exactly one TOM.
- `SPONT`: Additional brands mentioned without prompting (bq1b). Rank 1 = first additional mention.
- `AIDED`: Brands recognised when shown a list (bq1c). Rank is NULL (screen-selection, order not meaningful).

### v_brand_nps
One row per respondent × brand rated. NPS score 0-10.

| Column | Type | Description |
|--------|------|-------------|
| respondent_id | INT | |
| brand_id, brand_name | | |
| nps_score | INT | 0-10 (0=would not recommend, 10=definitely recommend) |
| nps_category | TEXT | 'Promoter' (9-10) \| 'Passive' (7-8) \| 'Detractor' (0-6) |
| gender, age, age_band, city_name, zone_name, interview_* | | |

**Note:** Sparsely populated — a respondent only has a score for brands they've used/owned.

### v_kitchen_ownership
One row per respondent × kitchen appliance owned (mq3a).

| Column | Type | Description |
|--------|------|-------------|
| respondent_id | INT | |
| appliance_id, appliance_name | | Kitchen appliance (Mixer Grinder, Juicer, etc.) |
| gender, age, age_band, city_name, zone_name, interview_* | | |

### v_recent_purchase
One row per respondent × recently purchased kitchen appliance (mq3b). Ranked — up to 3 per respondent.

| Column | Type | Description |
|--------|------|-------------|
| respondent_id | INT | |
| purchase_rank | INT | 1=most recent/primary, 2, 3 |
| appliance_id, appliance_name | | Kitchen appliance |
| gender, age, age_band, city_name, zone_name, interview_* | | |

### v_room_appliances
One row per respondent × room appliance owned (mq2a).

| Column | Type | Description |
|--------|------|-------------|
| respondent_id | INT | |
| appliance_id, appliance_name | | Room appliance (Ceiling Fans, AC, etc.) |
| gender, age, age_band, city_name, zone_name, interview_* | | |

---

## FACT TABLES (raw, for reference)

### fact_respondents
| Column | Type | Notes |
|--------|------|-------|
| respondent_id | INTEGER PK | 1-based row number from source |
| date_id | INT FK | → dim_date |
| city_id | INT FK | → dim_city (= centre code from survey) |
| zone_id | INT FK | → dim_zone |
| gender | TEXT | 'Male' / 'Female' |
| age | INT | |
| age_band | TEXT | '25-35' / '36-50' |
| interviewer | TEXT | |
| resp_name | TEXT | |
| device_id | TEXT | |
| category | TEXT | NULL in current data |

### fact_brand_awareness
| Column | Type | Notes |
|--------|------|-------|
| id | INT PK AUTOINCREMENT | |
| respondent_id | INT FK | |
| date_id | INT FK | |
| brand_id | INT FK | → dim_brand |
| stage | TEXT | 'TOM' / 'SPONT' / 'AIDED' |
| rank | INT | Position in response; NULL for AIDED |

### fact_brand_nps
| Column | Type | Notes |
|--------|------|-------|
| id | INT PK AUTOINCREMENT | |
| respondent_id | INT FK | |
| date_id | INT FK | |
| brand_id | INT FK | → dim_brand |
| nps_score | INT | 0-10 |

### fact_kitchen_ownership
| Column | Type | Notes |
|--------|------|-------|
| id | INT PK AUTOINCREMENT | |
| respondent_id | INT FK | |
| date_id | INT FK | |
| appliance_id | INT FK | → dim_kitchen_appliance |

### fact_recent_purchase
| Column | Type | Notes |
|--------|------|-------|
| id | INT PK AUTOINCREMENT | |
| respondent_id | INT FK | |
| date_id | INT FK | |
| appliance_id | INT FK | → dim_kitchen_appliance |
| purchase_rank | INT | 1=first/most recent |

### fact_room_appliances
| Column | Type | Notes |
|--------|------|-------|
| id | INT PK AUTOINCREMENT | |
| respondent_id | INT FK | |
| date_id | INT FK | |
| appliance_id | INT FK | → dim_room_appliance |

### fact_verbatims
| Column | Type | Notes |
|--------|------|-------|
| id | INT PK AUTOINCREMENT | |
| respondent_id | INT FK | |
| date_id | INT FK | |
| question_code | TEXT | 'bq2a', 'mq3a_others', etc. |
| question_label | TEXT | Human-readable question description |
| response_text | TEXT | Verbatim response (Hindi/English mix) |

---

## DIMENSION TABLES

### dim_date
| Column | Sample Values |
|--------|---------------|
| date_id | 1, 2, 3 … |
| full_date | '2021-04-06', '2021-04-07' … |
| year | 2021 |
| month_num | 4, 5, 6 |
| month_name | 'April', 'May', 'June' |
| quarter | 2 |
| day_of_week | 'Tuesday', 'Wednesday' … |

### dim_city (18 rows)
Delhi, Lucknow, Bikaner, Patiala, Chennai, Cochin, Guntur, Hassan,
Mumbai, Ahmedabad, Kolhapur, Ujjain, Kolkata, Patna, Bhubaneshwar,
Nagaon, Hyderabad, Bangalore

### dim_zone (4 rows)
North, South, West, East

### dim_brand (56 rows)
Codes 1-55 + 99 (Don't Know). See `config/project_1.py` for full mapping.
Top brands by TOM: Bajaj(1), Crompton(2), Usha(6), Havells(3), Philips(20).

### dim_kitchen_appliance (14 rows)
1=Mixer Grinder, 2=Juicer, 3=Food Processor, 4=Microwave Oven,
5=Electric Kettle, 6=Sandwich Maker, 7=Water Purifier, 8=Induction Stove,
9=Air Fryer, 10=OTG Oven, 11=Coffee Maker, 12=Electric Chimney,
13=Dishwasher, 14=Any Others

### dim_room_appliance (17 rows)
8=Ceiling Fans, 9=AC, 3=LED Tube Light, 4=LED Bulbs, 16=Air Cooler,
18=Water Heater/Geyser, 13=Table Fan, 11=Exhaust Fan, etc.
(Note: code 10 is intentionally absent — gap in source data)

---

## Common Query Patterns

```sql
-- Total respondents
SELECT COUNT(*) FROM fact_respondents;

-- Respondents by city
SELECT city_name, COUNT(*) n FROM v_respondents GROUP BY city_name ORDER BY n DESC;

-- TOM brand share
SELECT brand_name,
       COUNT(*) mentions,
       ROUND(COUNT(*)*100.0 / (SELECT COUNT(*) FROM fact_respondents), 1) pct
FROM v_brand_awareness
WHERE stage = 'TOM'
GROUP BY brand_name ORDER BY mentions DESC;

-- Average NPS by brand (min 50 ratings)
SELECT brand_name, ROUND(AVG(nps_score),1) avg_nps, COUNT(*) n
FROM v_brand_nps
GROUP BY brand_name HAVING n >= 50
ORDER BY avg_nps DESC;

-- Kitchen appliance ownership rate
SELECT appliance_name,
       COUNT(DISTINCT respondent_id) owners,
       ROUND(COUNT(DISTINCT respondent_id)*100.0 /
             (SELECT COUNT(*) FROM fact_respondents), 1) pct
FROM v_kitchen_ownership
GROUP BY appliance_name ORDER BY owners DESC;

-- Time-based: interviews by month
SELECT interview_month_name, COUNT(DISTINCT respondent_id) n
FROM v_respondents GROUP BY interview_month ORDER BY interview_month;
```
