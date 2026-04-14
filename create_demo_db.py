"""
Create a minimal demo database for OxData.
This can be committed to the repo to demonstrate the app works.
"""

import sqlite3
from pathlib import Path
import os

# Get database path from environment or default
DB_PATH = os.environ.get('DB_PATH', 'data/project_1/oxdata.db')

def create_demo_db(db_path):
    """Create a minimal demo database with sample data."""
    
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create dimension tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS dim_brand (
            brand_id INTEGER PRIMARY KEY,
            brand_name TEXT NOT NULL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS dim_city (
            city_id INTEGER PRIMARY KEY,
            city_name TEXT NOT NULL,
            zone_name TEXT
        )
    ''')
    
    # Create respondent fact table
    c.execute('''
        CREATE TABLE IF NOT EXISTS fact_respondents (
            respondent_id INTEGER PRIMARY KEY,
            gender TEXT,
            age INTEGER,
            age_band TEXT,
            city_name TEXT,
            zone_name TEXT,
            interview_date TEXT
        )
    ''')
    
    # Create awareness fact table
    c.execute('''
        CREATE TABLE IF NOT EXISTS fact_brand_awareness (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            respondent_id INTEGER,
            brand_name TEXT,
            stage TEXT,
            rank INTEGER
        )
    ''')
    
    # Create NPS fact table
    c.execute('''
        CREATE TABLE IF NOT EXISTS fact_brand_nps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            respondent_id INTEGER,
            brand_name TEXT,
            nps_score INTEGER,
            nps_category TEXT
        )
    ''')
    
    # Create ownership fact table
    c.execute('''
        CREATE TABLE IF NOT EXISTS fact_kitchen_ownership (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            respondent_id INTEGER,
            appliance_name TEXT,
            city_name TEXT,
            gender TEXT,
            age_band TEXT,
            zone_name TEXT
        )
    ''')
    
    # Create purchase fact table
    c.execute('''
        CREATE TABLE IF NOT EXISTS fact_recent_purchase (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            respondent_id INTEGER,
            appliance_name TEXT,
            purchase_rank INTEGER,
            gender TEXT,
            age_band TEXT
        )
    ''')
    
    # Insert sample brands
    brands = [('Crompton',), ('Bajaj',), ('Havells',), ('Philips',), ('Usha',)]
    c.executemany('INSERT INTO dim_brand (brand_name) VALUES (?)', brands)
    
    # Insert sample cities
    cities = [
        ('Mumbai', 'West'), ('Delhi', 'North'), ('Bangalore', 'South'),
        ('Kolkata', 'East'), ('Chennai', 'South'), ('Hyderabad', 'South'),
        ('Ahmedabad', 'West'), ('Lucknow', 'North'), ('Patna', 'East'),
        ('Bhubaneshwar', 'East')
    ]
    c.executemany('INSERT INTO dim_city (city_name, zone_name) VALUES (?, ?)', cities)
    
    # Generate sample respondents (100 sample records)
    import random
    genders = ['Male', 'Female']
    age_bands = ['18-24', '25-35', '36-50', '51+']
    city_list = [r[0] for r in c.execute('SELECT city_name FROM dim_city').fetchall()]
    zone_list = [r[0] for r in c.execute('SELECT zone_name FROM dim_city').fetchall()]
    
    respondents = []
    for i in range(1, 101):
        respondents.append((
            i,
            random.choice(genders),
            random.randint(18, 60),
            random.choice(age_bands),
            random.choice(city_list),
            random.choice(zone_list),
            '2025-01-' + str(random.randint(1, 28)).zfill(2)
        ))
    c.executemany('''
        INSERT INTO fact_respondents 
        (respondent_id, gender, age, age_band, city_name, zone_name, interview_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', respondents)
    
    # Generate sample awareness data
    brand_list = [r[0] for r in c.execute('SELECT brand_name FROM dim_brand').fetchall()]
    stages = ['TOM', 'SPONT', 'AIDED']
    
    awareness_data = []
    for resp_id in range(1, 101):
        # Each respondent aware of 2-4 brands
        aware_brands = random.sample(brand_list, random.randint(2, 4))
        for brand in aware_brands:
            stage = random.choice(stages)
            rank = random.randint(1, 5) if stage == 'TOM' else None
            awareness_data.append((resp_id, brand, stage, rank))
    
    c.executemany('''
        INSERT INTO fact_brand_awareness 
        (respondent_id, brand_name, stage, rank)
        VALUES (?, ?, ?, ?)
    ''', awareness_data)
    
    # Generate sample NPS data
    nps_data = []
    for resp_id in range(1, 101):
        # Each respondent rates 2 brands
        rated_brands = random.sample(brand_list, 2)
        for brand in rated_brands:
            score = random.randint(1, 10)
            if score >= 9:
                category = 'Promoter'
            elif score >= 7:
                category = 'Passive'
            else:
                category = 'Detractor'
            nps_data.append((resp_id, brand, score, category))
    
    c.executemany('''
        INSERT INTO fact_brand_nps 
        (respondent_id, brand_name, nps_score, nps_category)
        VALUES (?, ?, ?, ?)
    ''', nps_data)
    
    # Generate sample ownership data
    appliances = ['Mixer Grinder', 'Microwave', 'Kettle', 'Juicer', 'Food Processor']
    ownership_data = []
    for resp_id in range(1, 101):
        owned = random.sample(appliances, random.randint(1, 3))
        for app in owned:
            ownership_data.append((
                resp_id, app,
                random.choice(city_list), random.choice(genders),
                random.choice(age_bands), random.choice(zone_list)
            ))
    
    c.executemany('''
        INSERT INTO fact_kitchen_ownership 
        (respondent_id, appliance_name, city_name, gender, age_band, zone_name)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ownership_data)
    
    # Generate sample purchase data
    purchase_data = []
    for resp_id in range(1, 101):
        purchased = random.sample(appliances, random.randint(1, 2))
        for rank, app in enumerate(purchased, 1):
            purchase_data.append((
                resp_id, app, rank, random.choice(genders), random.choice(age_bands)
            ))
    
    c.executemany('''
        INSERT INTO fact_recent_purchase 
        (respondent_id, appliance_name, purchase_rank, gender, age_band)
        VALUES (?, ?, ?, ?, ?)
    ''', purchase_data)
    
    # Create views
    c.execute('''
        CREATE VIEW IF NOT EXISTS v_respondents AS
        SELECT * FROM fact_respondents
    ''')
    
    c.execute('''
        CREATE VIEW IF NOT EXISTS v_brand_awareness AS
        SELECT * FROM fact_brand_awareness
    ''')
    
    c.execute('''
        CREATE VIEW IF NOT EXISTS v_brand_nps AS
        SELECT * FROM fact_brand_nps
    ''')
    
    c.execute('''
        CREATE VIEW IF NOT EXISTS v_kitchen_ownership AS
        SELECT * FROM fact_kitchen_ownership
    ''')
    
    c.execute('''
        CREATE VIEW IF NOT EXISTS v_recent_purchase AS
        SELECT * FROM fact_recent_purchase
    ''')
    
    conn.commit()
    conn.close()
    
    print(f'Demo database created at: {db_path}')

if __name__ == '__main__':
    create_demo_db(DB_PATH)