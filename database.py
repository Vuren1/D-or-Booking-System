import sqlite3
import pandas as pd
from datetime import datetime
import os

# Database setup
DB_NAME = "data/bookings.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()

    # ... je andere tabellen

    # Nieuwe tabel voor sms-herinneringsinstellingen
    c.execute("""
        CREATE TABLE IF NOT EXISTS sms_settings (
            company_id INTEGER PRIMARY KEY,
            days_before INTEGER DEFAULT 1,
            hours_before INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()
    
    # Tabel voor diensten per bedrijf
    c.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT,
            price REAL,
            duration INTEGER,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    ''')
    
    # Tabel voor beschikbaarheid per bedrijf
    c.execute('''
        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            day TEXT,
            start_time TEXT,
            end_time TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    ''')
    
    # Tabel voor boekingen per bedrijf
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT,
            phone TEXT,
            service_id INTEGER,
            date TEXT,
            time TEXT,
            status TEXT DEFAULT 'bevestigd',
            created_at TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def add_company(name, email, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    c.execute("INSERT INTO companies (name, email, password, created_at) VALUES (?, ?, ?, ?)",
              (name, email, password, created_at))
    conn.commit()
    company_id = c.lastrowid
    conn.close()
    return company_id

def get_company_by_email(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE email = ?", (email,))
    company = c.fetchone()
    conn.close()
    return company

def add_service(company_id, name, price, duration):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO services (company_id, name, price, duration) VALUES (?, ?, ?, ?)",
              (company_id, name, price, duration))
    conn.commit()
    conn.close()

def get_services(company_id):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM services WHERE company_id = ?", conn, params=(company_id,))
    conn.close()
    return df

def add_availability(company_id, day, start_time, end_time):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO availability (company_id, day, start_time, end_time) VALUES (?, ?, ?, ?)",
              (company_id, day, start_time, end_time))
    conn.commit()
    conn.close()

def get_availability(company_id):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM availability WHERE company_id = ?", conn, params=(company_id,))
    conn.close()
    return df

def add_booking(company_id, name, phone, service_id, date, time):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    c.execute("""
        INSERT INTO bookings (company_id, name, phone, service_id, date, time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (company_id, name, phone, service_id, date, time, created_at))
    conn.commit()
    booking_id = c.lastrowid
    conn.close()
    return booking_id

def get_bookings(company_id):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM bookings WHERE company_id = ? ORDER BY date DESC, time DESC", conn, params=(company_id,))
    conn.close()
    return df

def get_available_slots(company_id, date):
    availability = get_availability(company_id)
    if availability.empty:
        return []
    # Simpele logica: Neem slots van de eerste beschikbare rij (uitbreiden voor dag-specifiek)
    row = availability.iloc[0]
    start = pd.Timestamp(f"{date} {row['start_time']}")
    end = pd.Timestamp(f"{date} {row['end_time']}")
    slots = []
    current = start
    while current < end:
        slot_time = current.strftime("%H:%M")
        slots.append(slot_time)
        current += pd.Timedelta(minutes=30)  # 30 min slots
    return slots

def update_company_paid(company_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE companies SET paid = 1 WHERE id = ?", (company_id,))
    conn.commit()
    conn.close()

def is_company_paid(company_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT paid FROM companies WHERE id = ?", (company_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0
