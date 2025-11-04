# database.py
import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd

DB_NAME = "data/bookings.db"
os.makedirs("data", exist_ok=True)

# ---------------------------
# Helpers
# ---------------------------

def _ensure_service_extra_columns(conn: sqlite3.Connection):
    """
    Zorgt dat services tabel de kolommen category en description heeft.
    (handig bij oude DB's)
    """
    c = conn.cursor()
    c.execute("PRAGMA table_info(services)")
    cols = {row[1] for row in c.fetchall()}
    if "category" not in cols:
        c.execute("ALTER TABLE services ADD COLUMN category TEXT DEFAULT 'Algemeen'")
    if "description" not in cols:
        c.execute("ALTER TABLE services ADD COLUMN description TEXT DEFAULT ''")
    conn.commit()

def _ensure_indexes(conn: sqlite3.Connection):
    c = conn.cursor()
    # Snelle lookups
    c.execute("CREATE INDEX IF NOT EXISTS idx_services_company ON services(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_avail_company ON availability(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_company ON bookings(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_booking_items_booking ON booking_items(booking_id)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_unique ON categories(company_id, name)")
    conn.commit()

# ---------------------------
# Init database
# ---------------------------

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Bedrijven (tenants)
    c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            password TEXT,
            paid INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    # Categorieën (met beschrijving)
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT,
            description TEXT,
            UNIQUE(company_id, name),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # Diensten (met category/description)
    c.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT,
            price REAL,
            duration INTEGER,
            category TEXT,
            description TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)
    _ensure_service_extra_columns(conn)

    # Beschikbaarheid
    c.execute("""
        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            day TEXT,
            start_time TEXT,
            end_time TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # Boekingen (met totalen)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            customer_name TEXT,
            phone TEXT,
            date TEXT,
            time TEXT,
            total_price REAL,
            total_duration INTEGER,
            created_at TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # Gekozen diensten bij een boeking
    c.execute("""
        CREATE TABLE IF NOT EXISTS booking_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER,
            service_id INTEGER,
            FOREIGN KEY (booking_id) REFERENCES bookings(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    """)

    _ensure_indexes(conn)
    conn.commit()
    conn.close()

# ---------------------------
# Companies
# ---------------------------

def add_company(name, email, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    c.execute(
        "INSERT INTO companies (name, email, password, created_at) VALUES (?, ?, ?, ?)",
        (name, email, password, created_at),
    )
    conn.commit()
    company_id = c.lastrowid
    conn.close()
    return company_id

def get_company_by_email(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return row

def get_company_by_id(company_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_company_paid(company_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE companies SET paid = 1 WHERE id = ?", (company_id,))
    conn.commit()
    conn.close()

def is_company_paid(company_id: int) -> int:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT paid FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

# ---------------------------
# Categories
# ---------------------------

def upsert_category(company_id: int, name: str, description: str = ""):
    """Insert of update (beschrijving)."""
    name = (name or "").strip() or "Algemeen"
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO categories (company_id, name, description)
        VALUES (?, ?, ?)
        ON CONFLICT(company_id, name) DO UPDATE SET description=excluded.description
    """, (company_id, name, description or ""))
    conn.commit()
    conn.close()

def get_categories(company_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT name, description FROM categories WHERE company_id = ? ORDER BY name",
        conn, params=(company_id,)
    )
    conn.close()
    # Zorg dat Algemeen er altijd is (ook als leeg)
    if df.empty or "Algemeen" not in df["name"].tolist():
        df = pd.concat([pd.DataFrame([{"name": "Algemeen", "description": ""}]), df], ignore_index=True)
    return df

def get_category_description(company_id: int, name: str) -> str:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT description FROM categories WHERE company_id = ? AND name = ?", (company_id, name))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

# ---------------------------
# Services
# ---------------------------

def add_service(company_id: int, name: str, price: float, duration: int,
                category: str = "Algemeen", description: str = ""):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO services (company_id, name, price, duration, category, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (company_id, name, float(price), int(duration), category or "Algemeen", description or ""))
    conn.commit()
    conn.close()

def get_services(company_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT id, company_id, name, price, duration, category, description FROM services WHERE company_id = ? ORDER BY category, name",
        conn, params=(company_id,)
    )
    conn.close()
    return df

def get_service_categories(company_id: int) -> list:
    df = get_services(company_id)
    if df.empty:
        return []
    return sorted(df["category"].dropna().unique().tolist())

def get_services_by_ids(service_ids: list) -> pd.DataFrame:
    if not service_ids:
        return pd.DataFrame()
    conn = sqlite3.connect(DB_NAME)
    q = "SELECT id, company_id, name, price, duration, category, description FROM services WHERE id IN ({})".format(
        ",".join("?" * len(service_ids))
    )
    df = pd.read_sql_query(q, conn, params=tuple(service_ids))
    conn.close()
    return df

def update_service(service_id: int, name: str, price: float, duration: int,
                   category: str, description: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        UPDATE services
           SET name = ?, price = ?, duration = ?, category = ?, description = ?
         WHERE id = ?
    """, (name, float(price), int(duration), category, description, int(service_id)))
    conn.commit()
    conn.close()

def delete_service(service_id: int):
    """Verwijder een dienst (zonder referentie-check)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM services WHERE id = ?", (int(service_id),))
    conn.commit()
    conn.close()

# ---------------------------
# Availability & Slots
# ---------------------------

_DUTCH_DAYS = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]

def add_availability(company_id: int, day: str, start_time: str, end_time: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO availability (company_id, day, start_time, end_time)
        VALUES (?, ?, ?, ?)
    """, (company_id, day, start_time, end_time))
    conn.commit()
    conn.close()

def get_availability(company_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT id, company_id, day, start_time, end_time FROM availability WHERE company_id = ? ORDER BY id DESC",
        conn, params=(company_id,)
    )
    conn.close()
    return df

def _parse_hhmm(s: str) -> datetime:
    # Geef een dummy datum terug met de tijd gevuld
    return datetime.strptime(s, "%H:%M")

def _overlaps(start_a: datetime, dur_a_min: int, start_b: datetime, dur_b_min: int) -> bool:
    end_a = start_a + timedelta(minutes=dur_a_min)
    end_b = start_b + timedelta(minutes=dur_b_min)
    return (start_a < end_b) and (start_b < end_a)

def _company_bookings_on_date(company_id: int, date_str: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT time, total_duration FROM bookings WHERE company_id = ? AND date = ?",
        conn, params=(company_id, date_str)
    )
    conn.close()
    return df

def get_available_slots(company_id: int, date_str: str, step_minutes: int = 30) -> list:
    """
    Eenvoudige slots op basis van eerste beschikbaarheidsregel.
    (Backward-compat, gebruikt in oude flows)
    """
    avail = get_availability(company_id)
    if avail.empty:
        return []
    # Neem eerste regel (je kunt dit uitbreiden naar dag-specifiek)
    row = avail.iloc[0]
    start = _parse_hhmm(row["start_time"])
    end = _parse_hhmm(row["end_time"])
    slots = []
    t = start
    while t < end:
        slots.append(t.strftime("%H:%M"))
        t += timedelta(minutes=step_minutes)
    return slots

def get_available_slots_for_duration(company_id: int, date_str: str, total_duration: int, step: int = 5) -> list:
    """
    Berekent tijdslots voor een specifieke datum waarin een blok van total_duration past,
    rekening houdend met bestaande boekingen.
    step = 5 minuten, zodat korte diensten mogelijk zijn.
    """
    # Welke dag van de week?
    try:
        weekday_idx = pd.Timestamp(date_str).weekday()  # 0 = maandag
        day_name = _DUTCH_DAYS[weekday_idx]
    except Exception:
        # fallback: toon niets
        return []

    avail = get_availability(company_id)
    if avail.empty:
        return []

    day_rows = avail[avail["day"] == day_name]
    if day_rows.empty:
        return []

    # Haal boekingen op die dag op (om overlap te vermijden)
    day_bookings = _company_bookings_on_date(company_id, date_str)

    slots = []
    for _, row in day_rows.iterrows():
        st = _parse_hhmm(row["start_time"])
        en = _parse_hhmm(row["end_time"])
        t = st
        while (t + timedelta(minutes=total_duration)) <= en:
            # Check overlap met bestaande boekingen
            can_place = True
            for _, b in day_bookings.iterrows():
                b_start = datetime.strptime(b["time"], "%H:%M")
                if _overlaps(t, total_duration, b_start, int(b["total_duration"])):
                    can_place = False
                    break
            if can_place:
                slots.append(t.strftime("%H:%M"))
            t += timedelta(minutes=step)

    return sorted(list(dict.fromkeys(slots)))  # unieke, gesorteerde lijst

# ---------------------------
# Bookings
# ---------------------------

def add_booking_with_items(company_id: int, customer_name: str, phone: str,
                           service_ids: list, date_str: str, time_str: str) -> int:
    """
    Slaat een boeking op + alle gekozen services in booking_items.
    Berekent automatisch totalen.
    """
    sel_df = get_services_by_ids(service_ids)
    total_price = float(sel_df["price"].sum()) if not sel_df.empty else 0.0
    total_duration = int(sel_df["duration"].sum()) if not sel_df.empty else 0

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    created_at = datetime.now().isoformat()

    c.execute("""
        INSERT INTO bookings (company_id, customer_name, phone, date, time, total_price, total_duration, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (company_id, customer_name, phone, date_str, time_str, total_price, total_duration, created_at))
    booking_id = c.lastrowid

    for sid in service_ids:
        c.execute("INSERT INTO booking_items (booking_id, service_id) VALUES (?, ?)", (booking_id, int(sid)))

    conn.commit()
    conn.close()
    return booking_id

def get_bookings_overview(company_id: int) -> pd.DataFrame:
    """
    Overzicht met boekingen en (samengevoegde) dienstenamen.
    """
    conn = sqlite3.connect(DB_NAME)
    # Haal bookings op
    bookings = pd.read_sql_query("""
        SELECT id, customer_name, phone, date, time, total_price, total_duration, created_at
          FROM bookings
         WHERE company_id = ?
         ORDER BY date DESC, time DESC, id DESC
    """, conn, params=(company_id,))

    if bookings.empty:
        conn.close()
        return bookings

    # Items + dienstenamen
    items = pd.read_sql_query("""
        SELECT bi.booking_id, s.name AS service_name
          FROM booking_items bi
          JOIN services s ON s.id = bi.service_id
         WHERE s.company_id = ?
    """, conn, params=(company_id,))

    conn.close()

    if items.empty:
        bookings["services"] = ""
        return bookings

    grouped = items.groupby("booking_id")["service_name"].apply(lambda x: ", ".join(x)).reset_index()
    grouped.columns = ["id", "services"]
    out = bookings.merge(grouped, how="left", on="id")
    out["services"] = out["services"].fillna("")
    return out
