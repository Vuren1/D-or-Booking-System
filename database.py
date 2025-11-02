import sqlite3
import pandas as pd
from datetime import datetime
import os

DB_NAME = "data/bookings.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabel voor bedrijven (tenants)
    c.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            password TEXT,
            created_at TEXT
        )
    ''')
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

# Functies om diensten toe te voegen, beschikbaarheid, etc. (we voegen later toe)
