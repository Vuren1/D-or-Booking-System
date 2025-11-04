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
    """
    Maakt 30-minuten-slots voor de gekozen datum.
    Zoekt eerst naar beschikbaarheid met de NL-dagnaam (Maandag, ...).
    Gebruik geen locale op de server om errors te voorkomen.
    """
    avail = get_availability(company_id)
    if avail.empty:
        return []

    # Bepaal dagnaam in het Engels en map naar NL (zonder locale afhankelijkheid)
    eng_day = pd.Timestamp(date).day_name()  # bv. 'Monday'
    eng_to_nl = {
        "Monday": "Maandag",
        "Tuesday": "Dinsdag",
        "Wednesday": "Woensdag",
        "Thursday": "Donderdag",
        "Friday": "Vrijdag",
        "Saturday": "Zaterdag",
        "Sunday": "Zondag",
    }
    target_day = eng_to_nl.get(eng_day, eng_day)

    # Zoek beschikbaarheid voor die dag; anders fallback naar eerste rij
    row = None
    if "day" in avail.columns:
        match = avail[avail["day"] == target_day]
        if not match.empty:
            row = match.iloc[0]
    if row is None:
        row = avail.iloc[0]

    # Bouw tijdslots
    start = pd.Timestamp(f"{date} {row['start_time']}")
    end = pd.Timestamp(f"{date} {row['end_time']}")
    slots = []
    cur = start
    while cur < end:
        slots.append(cur.strftime("%H:%M"))
        cur += pd.Timedelta(minutes=30)  # pas aan indien je andere slotgrootte wil
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

    # Services (met category)
    c.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name       TEXT NOT NULL,
            price      REAL NOT NULL DEFAULT 0,
            duration   INTEGER NOT NULL DEFAULT 30,
            category   TEXT DEFAULT 'Algemeen',
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

    # Bookings: nu met total_price/total_duration
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

    # Booking items (meerdere diensten per booking)
    c.execute("""
        CREATE TABLE IF NOT EXISTS booking_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id  INTEGER NOT NULL,
            service_id  INTEGER NOT NULL,
            FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        )
    """)

    # SMS settings (optioneel)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sms_settings (
            company_id   INTEGER PRIMARY KEY,
            days_before  INTEGER DEFAULT 1,
            hours_before INTEGER DEFAULT 1,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Migrations (voor bestaande DB's)
    # Voeg category aan services als die nog niet bestaat
    try:
        c.execute("ALTER TABLE services ADD COLUMN category TEXT DEFAULT 'Algemeen'")
    except sqlite3.OperationalError:
        pass
    # Voeg total_price/total_duration aan bookings
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

# ---------- Services ----------
def add_service(company_id, name, price, duration, category="Algemeen"):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO services (company_id, name, price, duration, category) VALUES (?, ?, ?, ?, ?)",
        (company_id, name, float(price), int(duration), category or "Algemeen")
    )
    conn.commit()
    conn.close()

def get_services(company_id) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT id, name, price, duration, category FROM services WHERE company_id = ? ORDER BY category, name",
        conn, params=(company_id,)
    )
    conn.close()
    return df

def get_service_categories(company_id) -> list:
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT DISTINCT category FROM services WHERE company_id = ? ORDER BY category",
        conn, params=(company_id,)
    )
    conn.close()
    return df["category"].tolist()

def get_services_by_ids(service_ids: list[int]) -> pd.DataFrame:
    if not service_ids:
        return pd.DataFrame(columns=["id","name","price","duration","category"])
    conn = _connect()
    qmarks = ",".join("?" for _ in service_ids)
    df = pd.read_sql_query(
        f"SELECT id, name, price, duration, category FROM services WHERE id IN ({qmarks})",
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

# ---------- Slots (30-min, NL dagnaam zonder locale) ----------
def _nl_day(date: str) -> str:
    eng_day = pd.Timestamp(date).day_name()
    return {
        "Monday": "Maandag",
        "Tuesday": "Dinsdag",
        "Wednesday": "Woensdag",
        "Thursday": "Donderdag",
        "Friday": "Vrijdag",
        "Saturday": "Zaterdag",
        "Sunday": "Zondag",
    }.get(eng_day, eng_day)

def get_available_slots(company_id: int, date: str) -> list[str]:
    avail = get_availability(company_id)
    if avail.empty:
        return []
    target_day = _nl_day(date)

    row = None
    m = avail[avail["day"] == target_day]
    if not m.empty:
        row = m.iloc[0]
    else:
        row = avail.iloc[0]

    start = pd.Timestamp(f"{date} {row['start_time']}")
    end   = pd.Timestamp(f"{date} {row['end_time']}")
    slots = []
    cur = start
    while cur < end:
        slots.append(cur.strftime("%H:%M"))
        cur += pd.Timedelta(minutes=30)
    return slots

def get_available_slots_for_duration(company_id: int, date: str, total_minutes: int) -> list[str]:
    """
    Vind starttijden waarop een blok van total_minutes in de beschikbaarheid past,
    uitgaande van 30-min stappen voor starttijd.
    """
    if total_minutes <= 0:
        return get_available_slots(company_id, date)

    avail = get_availability(company_id)
    if avail.empty:
        return []
    target_day = _nl_day(date)
    row = None
    m = avail[avail["day"] == target_day]
    row = m.iloc[0] if not m.empty else avail.iloc[0]

    start = pd.Timestamp(f"{date} {row['start_time']}")
    end   = pd.Timestamp(f"{date} {row['end_time']}")
    block = pd.Timedelta(minutes=int(total_minutes))

    slots = []
    cur = start
    while cur + block <= end:
        slots.append(cur.strftime("%H:%M"))
        cur += pd.Timedelta(minutes=30)  # startstap blijft 30m
    return slots

# ---------- Bookings (met meerdere services) ----------
def add_booking_with_items(company_id: int, name: str, phone: str, service_ids: list[int], date: str, time: str) -> int:
    """Maak één booking met meerdere services (booking_items), sla ook totalen op."""
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
        c.execute(
            "INSERT INTO booking_items (booking_id, service_id) VALUES (?, ?)",
            (booking_id, sid)
        )

    conn.commit()
    conn.close()
    return booking_id
