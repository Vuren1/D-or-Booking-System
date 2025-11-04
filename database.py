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
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = _connect()
    c = conn.cursor()

    # Companies
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

    # Service categories (met beschrijving)
    c.execute("""
        CREATE TABLE IF NOT EXISTS service_categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER NOT NULL,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            UNIQUE(company_id, name),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Services (nu mét description + category-naam)
    c.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name       TEXT NOT NULL,
            price      REAL NOT NULL DEFAULT 0,
            duration   INTEGER NOT NULL DEFAULT 30,
            category   TEXT DEFAULT 'Algemeen',
            description TEXT DEFAULT '',
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Availability
    c.execute("""
        CREATE TABLE IF NOT EXISTS availability (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            day        TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time   TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Bookings met totalen
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id     INTEGER NOT NULL,
            name           TEXT NOT NULL,
            phone          TEXT NOT NULL,
            date           TEXT NOT NULL,
            time           TEXT NOT NULL,
            total_price    REAL DEFAULT 0,
            total_duration INTEGER DEFAULT 0,
            status         TEXT DEFAULT 'bevestigd',
            created_at     TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Losse services per booking
    c.execute("""
        CREATE TABLE IF NOT EXISTS booking_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id  INTEGER NOT NULL,
            service_id  INTEGER NOT NULL,
            FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        )
    """)

    # Optionele sms-instellingen (later handig)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sms_settings (
            company_id   INTEGER PRIMARY KEY,
            days_before  INTEGER DEFAULT 1,
            hours_before INTEGER DEFAULT 1,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # --- Migrations (veilig proberen) ---
    try:
        c.execute("ALTER TABLE services ADD COLUMN category TEXT DEFAULT 'Algemeen'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE services ADD COLUMN description TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN total_price REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN total_duration INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

# ---------- Companies ----------
def add_company(name, email, password):
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

def get_company_by_email(email):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return row

def get_company_by_id(company_id):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_company_paid(company_id):
    conn = _connect()
    c = conn.cursor()
    c.execute("UPDATE companies SET paid = 1 WHERE id = ?", (company_id,))
    conn.commit()
    conn.close()

def is_company_paid(company_id) -> int:
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT COALESCE(paid,0) FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

# ---------- Categories ----------
def upsert_category(company_id: int, name: str, description: str = ""):
    """Maak of update een categorie (uniek per company + naam)."""
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        INSERT INTO service_categories (company_id, name, description)
        VALUES (?, ?, ?)
        ON CONFLICT(company_id, name) DO UPDATE SET description = excluded.description
    """, (company_id, name.strip(), description or ""))
    conn.commit()
    conn.close()

def get_categories(company_id: int) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT name, description FROM service_categories WHERE company_id = ? ORDER BY name",
        conn, params=(company_id,)
    )
    conn.close()
    return df

def get_category_description(company_id: int, name: str) -> str:
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "SELECT description FROM service_categories WHERE company_id = ? AND name = ?",
        (company_id, name),
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

# ---------- Services ----------
def add_service(company_id, name, price, duration, category="Algemeen", description=""):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO services (company_id, name, price, duration, category, description) VALUES (?, ?, ?, ?, ?, ?)",
        (company_id, name, float(price), int(duration), category or "Algemeen", description or "")
    )
    conn.commit()
    conn.close()

def get_services(company_id) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT id, name, price, duration, category, description FROM services WHERE company_id = ? ORDER BY category, name",
        conn, params=(company_id,)
    )
    conn.close()
    return df

def get_service_categories(company_id) -> list:
    # Houdt rekening met services + losse categorie tabel
    cats = set(["Algemeen"])
    for c in get_categories(company_id)["name"].tolist():
        cats.add(c)
    conn = _connect()
    extra = pd.read_sql_query(
        "SELECT DISTINCT category FROM services WHERE company_id = ?",
        conn, params=(company_id,)
    )
    conn.close()
    for c in extra["category"].dropna().tolist():
        cats.add(c)
    return sorted(list(cats))

def get_services_by_ids(service_ids: list[int]) -> pd.DataFrame:
    if not service_ids:
        return pd.DataFrame(columns=["id","name","price","duration","category","description"])
    conn = _connect()
    qmarks = ",".join("?" for _ in service_ids)
    df = pd.read_sql_query(
        f"SELECT id, name, price, duration, category, description FROM services WHERE id IN ({qmarks})",
        conn, params=tuple(service_ids)
    )
    conn.close()
    return df

# ---------- Availability ----------
def add_availability(company_id, day, start_time, end_time):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO availability (company_id, day, start_time, end_time) VALUES (?, ?, ?, ?)",
        (company_id, day, start_time, end_time)
    )
    conn.commit()
    conn.close()

def get_availability(company_id) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT id, day, start_time, end_time FROM availability WHERE company_id = ? ORDER BY id DESC",
        conn, params=(company_id,)
    )
    conn.close()
    return df

# ---------- Slot helpers ----------
def _nl_day(date: str) -> str:
    eng_day = pd.Timestamp(date).day_name()
    return {
        "Monday": "Maandag", "Tuesday": "Dinsdag", "Wednesday": "Woensdag",
        "Thursday": "Donderdag", "Friday": "Vrijdag", "Saturday": "Zaterdag", "Sunday": "Zondag",
    }.get(eng_day, eng_day)

def get_available_slots(company_id: int, date: str) -> list[str]:
    avail = get_availability(company_id)
    if avail.empty:
        return []
    target_day = _nl_day(date)
    row = avail[avail["day"] == target_day].iloc[0] if not avail[avail["day"] == target_day].empty else avail.iloc[0]
    start = pd.Timestamp(f"{date} {row['start_time']}")
    end   = pd.Timestamp(f"{date} {row['end_time']}")
    slots = []
    cur = start
    while cur < end:
        slots.append(cur.strftime("%H:%M"))
        cur += pd.Timedelta(minutes=30)
    return slots

def get_available_slots_for_duration(company_id: int, date: str, total_minutes: int) -> list[str]:
    if total_minutes <= 0:
        return get_available_slots(company_id, date)
    avail = get_availability(company_id)
    if avail.empty:
        return []
    target_day = _nl_day(date)
    row = avail[avail["day"] == target_day].iloc[0] if not avail[avail["day"] == target_day].empty else avail.iloc[0]
    start = pd.Timestamp(f"{date} {row['start_time']}")
    end   = pd.Timestamp(f"{date} {row['end_time']}")
    block = pd.Timedelta(minutes=int(total_minutes))
    slots = []
    cur = start
    while cur + block <= end:
        slots.append(cur.strftime("%H:%M"))
        cur += pd.Timedelta(minutes=30)
    return slots

# ---------- Bookings ----------
def add_booking_with_items(company_id: int, name: str, phone: str, service_ids: list[int], date: str, time: str) -> int:
    services_df = get_services_by_ids(service_ids)
    total_price = float(services_df["price"].sum()) if not services_df.empty else 0.0
    total_duration = int(services_df["duration"].sum()) if not services_df.empty else 0

    conn = _connect()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO bookings (company_id, name, phone, date, time, total_price, total_duration, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (company_id, name, phone, date, time, total_price, total_duration, datetime.now().isoformat())
    )
    booking_id = c.lastrowid

    for sid in service_ids:
        c.execute("INSERT INTO booking_items (booking_id, service_id) VALUES (?, ?)", (booking_id, sid))

    conn.commit()
    conn.close()
    return booking_id

def get_bookings_overview(company_id: int) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        """
        SELECT 
            b.id,
            b.date,
            b.time,
            b.name  AS customer_name,
            b.phone,
            ROUND(b.total_price, 2) AS total_price,
            b.total_duration,
            GROUP_CONCAT(s.name, ', ') AS services
        FROM bookings b
        LEFT JOIN booking_items bi ON bi.booking_id = b.id
        LEFT JOIN services s       ON s.id = bi.service_id
        WHERE b.company_id = ?
        GROUP BY b.id
        ORDER BY b.date DESC, b.time DESC, b.id DESC
        """,
        conn, params=(company_id,)
    )
    conn.close()
    return df
