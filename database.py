# database.py
import os
import sqlite3
from datetime import datetime
import pandas as pd

DB_DIR = "data"
DB_NAME = os.path.join(DB_DIR, "bookings.db")
os.makedirs(DB_DIR, exist_ok=True)

def _connect():
    conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
    # Zorg dat foreign keys ook echt enforced worden
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Maak alle tabellen aan als ze nog niet bestaan."""
    conn = _connect()
    c = conn.cursor()

    # Bedrijven (tenants)
    c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT UNIQUE,
            password   TEXT,
            paid       INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    # Diensten per bedrijf
    c.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name       TEXT NOT NULL,
            price      REAL NOT NULL DEFAULT 0,
            duration   INTEGER NOT NULL DEFAULT 30,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Beschikbaarheid per bedrijf
    c.execute("""
        CREATE TABLE IF NOT EXISTS availability (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            day        TEXT NOT NULL,          -- bijv. 'Maandag'
            start_time TEXT NOT NULL,          -- '09:00'
            end_time   TEXT NOT NULL,          -- '18:00'
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Boekingentabel
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name       TEXT NOT NULL,
            phone      TEXT NOT NULL,
            service_id INTEGER NOT NULL,
            date       TEXT NOT NULL,          -- 'YYYY-MM-DD'
            time       TEXT NOT NULL,          -- 'HH:MM'
            status     TEXT DEFAULT 'bevestigd',
            created_at TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        )
    """)

    # optionele instellingen voor herinneringen (dag/uur voor de afspraak)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sms_settings (
            company_id  INTEGER PRIMARY KEY,
            days_before INTEGER DEFAULT 1,
            hours_before INTEGER DEFAULT 1,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()

# ---------- Companies ----------
def add_company(name: str, email: str, password: str) -> int:
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO companies (name, email, password, created_at) VALUES (?, ?, ?, ?)",
        (name, email, password, datetime.now().isoformat())
    )
    conn.commit()
    cid = c.lastrowid
    conn.close()
    return cid

def get_company_by_email(email: str):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return row

def get_company_by_id(company_id: int):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_company_paid(company_id: int):
    conn = _connect()
    c = conn.cursor()
    c.execute("UPDATE companies SET paid = 1 WHERE id = ?", (company_id,))
    conn.commit()
    conn.close()

def is_company_paid(company_id: int) -> int:
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT COALESCE(paid,0) FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

# ---------- Services ----------
def add_service(company_id: int, name: str, price: float, duration: int):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO services (company_id, name, price, duration) VALUES (?, ?, ?, ?)",
        (company_id, name, float(price), int(duration))
    )
    conn.commit()
    conn.close()

def get_services(company_id: int) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT id, name, price, duration FROM services WHERE company_id = ? ORDER BY id DESC",
        conn, params=(company_id,)
    )
    conn.close()
    return df

# ---------- Availability ----------
def add_availability(company_id: int, day: str, start_time: str, end_time: str):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO availability (company_id, day, start_time, end_time) VALUES (?, ?, ?, ?)",
        (company_id, day, start_time, end_time)
    )
    conn.commit()
    conn.close()

def get_availability(company_id: int) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT id, day, start_time, end_time FROM availability WHERE company_id = ? ORDER BY id DESC",
        conn, params=(company_id,)
    )
    conn.close()
    return df

# ---------- Bookings ----------
def add_booking(company_id: int, name: str, phone: str, service_id: int, date: str, time: str) -> int:
    conn = _connect()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO bookings (company_id, name, phone, service_id, date, time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (company_id, name, phone, service_id, date, time, datetime.now().isoformat())
    )
    conn.commit()
    bid = c.lastrowid
    conn.close()
    return bid

def get_bookings(company_id: int) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT * FROM bookings WHERE company_id = ? ORDER BY date DESC, time DESC",
        conn, params=(company_id,)
    )
    conn.close()
    return df

def get_available_slots(company_id: int, date: str) -> list[str]:
    """Eenvoudige slot-generator: pakt de eerste beschikbare regel voor die dagnaam en maakt 30-min slots."""
    avail = get_availability(company_id)
    if avail.empty:
        return []

    # Kies de rij met de juiste dag als die bestaat, anders eerste rij
    day_name = pd.Timestamp(date).day_name(locale='nl_BE') if hasattr(pd.Series, 'str') else pd.Timestamp(date).day_name()
    # Map Engelstalige day_name naar NL-lijst indien nodig
    nl_days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    map_days = dict(zip(nl_days, ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"]))
    target_day = map_days.get(day_name, day_name)

    row = None
    if "day" in avail.columns:
        m = avail[avail["day"] == target_day]
        if not m.empty:
            row = m.iloc[0]
    if row is None:
        row = avail.iloc[0]

    start = pd.Timestamp(f"{date} {row['start_time']}")
    end   = pd.Timestamp(f"{date} {row['end_time']}")
    slots = []
    cur = start
    while cur < end:
        slots.append(cur.strftime("%H:%M"))
        cur += pd.Timedelta(minutes=30)
    return slots

# ---------- SMS settings (optioneel) ----------
def get_sms_settings(company_id: int) -> tuple[int, int]:
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT days_before, hours_before FROM sms_settings WHERE company_id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row if row else (1, 1)

def update_sms_settings(company_id: int, days_before: int, hours_before: int):
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        INSERT INTO sms_settings (company_id, days_before, hours_before)
        VALUES (?, ?, ?)
        ON CONFLICT(company_id) DO UPDATE SET
            days_before = excluded.days_before,
            hours_before = excluded.hours_before
    """, (company_id, days_before, hours_before))
    conn.commit()
    conn.close()
