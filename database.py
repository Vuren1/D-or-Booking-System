import os
import sqlite3
from datetime import datetime, timedelta, time as dtime
import pandas as pd

# -------------------------------------------------
# Pad + DB bestand
# -------------------------------------------------
os.makedirs("data", exist_ok=True)
DB_NAME = "data/bookings.db"


# -------------------------------------------------
# Helper: migratie voor oude DB's
# -------------------------------------------------
def _ensure_booking_items_snapshot_columns(conn: sqlite3.Connection):
    """
    Zorgt dat booking_items de snapshot-kolommen heeft (name, price, duration).
    Hiermee blijven oude databases werken zonder dat je data wist.
    """
    c = conn.cursor()
    c.execute("PRAGMA table_info(booking_items)")
    cols = {row[1] for row in c.fetchall()}
    if "name" not in cols:
        c.execute("ALTER TABLE booking_items ADD COLUMN name TEXT")
    if "price" not in cols:
        c.execute("ALTER TABLE booking_items ADD COLUMN price REAL")
    if "duration" not in cols:
        c.execute("ALTER TABLE booking_items ADD COLUMN duration INTEGER")
    conn.commit()


# -------------------------------------------------
# DB init
# -------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Bedrijven
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

    # Categorieën met optionele beschrijving
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT,
            description TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # Diensten (incl. category + description)
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

    # Boekingen
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT,
            phone TEXT,
            date TEXT,         -- YYYY-MM-DD
            time TEXT,         -- HH:MM
            total_price REAL DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # Boekingsitems (met snapshot kolommen)
    c.execute("""
        CREATE TABLE IF NOT EXISTS booking_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER,
            service_id INTEGER,
            name TEXT,
            price REAL,
            duration INTEGER,
            FOREIGN KEY (booking_id) REFERENCES bookings(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    """)

    # ✅ Migratie-helper NA het creëren van booking_items
    _ensure_booking_items_snapshot_columns(conn)

    # Herinneringen-instellingen (voor sms/whatsapp)
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminder_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            enabled INTEGER DEFAULT 0,
            sms_enabled INTEGER DEFAULT 1,
            whatsapp_enabled INTEGER DEFAULT 0,
            days_before INTEGER DEFAULT 1,
            send_time TEXT DEFAULT '09:00',
            same_day_enabled INTEGER DEFAULT 0,
            same_day_minutes_before INTEGER DEFAULT 60,
            tz TEXT DEFAULT 'Europe/Brussels',
            template_day_before_sms TEXT,
            template_same_day_sms TEXT,
            template_day_before_wa TEXT,
            template_same_day_wa TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    conn.commit()
    conn.close()


# -------------------------------------------------
# Companies
# -------------------------------------------------
def add_company(name: str, email: str, password: str) -> int:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    c.execute(
        "INSERT INTO companies (name, email, password, created_at) VALUES (?,?,?,?)",
        (name, email, password, created_at),
    )
    conn.commit()
    company_id = c.lastrowid
    conn.close()
    return company_id


def get_company_by_email(email: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return row


def is_company_paid(company_id: int) -> int:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT paid FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def update_company_paid(company_id: int, paid: int = 1):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE companies SET paid = ? WHERE id = ?", (paid, company_id))
    conn.commit()
    conn.close()


def get_company_name_by_id(company_id: int) -> str:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else f"bedrijf #{company_id}"


# -------------------------------------------------
# Categories
# -------------------------------------------------
def add_category(company_id: int, name: str, description: str = ""):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO categories (company_id, name, description) VALUES (?,?,?)",
        (company_id, name, description),
    )
    conn.commit()
    conn.close()


def get_categories(company_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT * FROM categories WHERE company_id = ? ORDER BY name ASC",
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


def update_category(category_id: int, name: str, description: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "UPDATE categories SET name = ?, description = ? WHERE id = ?",
        (name, description, category_id),
    )
    conn.commit()
    conn.close()


def delete_category(category_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()


# -------------------------------------------------
# Services
# -------------------------------------------------
def add_service(company_id: int, name: str, price: float, duration: int, category: str, description: str = ""):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO services (company_id, name, price, duration, category, description) VALUES (?,?,?,?,?,?)",
        (company_id, name, price, duration, category, description),
    )
    conn.commit()
    conn.close()


def get_services(company_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT * FROM services WHERE company_id = ? ORDER BY category, name",
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


def update_service(service_id: int, name: str, price: float, duration: int, category: str, description: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "UPDATE services SET name=?, price=?, duration=?, category=?, description=? WHERE id=?",
        (name, price, duration, category, description, service_id),
    )
    conn.commit()
    conn.close()


def delete_service(service_id: int):
    """Verwijder service + eventuele ongebruikte booking_items verwijzingen blijven staan als snapshot (met name/price/duration)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM services WHERE id = ?", (service_id,))
    conn.commit()
    conn.close()


# -------------------------------------------------
# Availability
# -------------------------------------------------
def add_availability(company_id: int, day: str, start_time: str, end_time: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO availability (company_id, day, start_time, end_time) VALUES (?,?,?,?)",
        (company_id, day, start_time, end_time),
    )
    conn.commit()
    conn.close()


def get_availability(company_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT * FROM availability WHERE company_id = ?",
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


# -------------------------------------------------
# Slots helpers (zonder locale gedoe)
# -------------------------------------------------
_DUTCH_DAYS = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]


def _dayname_nl(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    return _DUTCH_DAYS[dt.weekday()]


def _to_dt(date_str: str, hhmm: str) -> datetime:
    return datetime.combine(datetime.strptime(date_str, "%Y-%m-%d").date(),
                            dtime.fromisoformat(hhmm))


def get_available_slots(company_id: int, date: str, duration_minutes: int = 30, step_minutes: int = 5) -> list[str]:
    """
    Eenvoudige slotgenerator: alle slots binnen de beschikbaarheid van die dag,
    in stappen van 5 min, waarbij het blok 'duration_minutes' in de dag past.
    (Houdt geen rekening met bestaande boekingen – dat kan later uitgebreid worden.)
    """
    avail = get_availability(company_id)
    if avail.empty:
        return []

    dayname = _dayname_nl(date)
    day_rows = avail[avail["day"] == dayname]
    if day_rows.empty:
        return []

    slots = []
    for _, row in day_rows.iterrows():
        start_dt = _to_dt(date, row["start_time"])
        end_dt = _to_dt(date, row["end_time"])
        cursor = start_dt
        while cursor + timedelta(minutes=duration_minutes) <= end_dt:
            slots.append(cursor.strftime("%H:%M"))
            cursor += timedelta(minutes=step_minutes)
    return sorted(slots)


def get_available_slots_for_duration(company_id: int, date: str, total_minutes: int, step_minutes: int = 5) -> list[str]:
    """Zelfde als hierboven, maar voor samengestelde duur (som van geselecteerde diensten)."""
    return get_available_slots(company_id, date, duration_minutes=total_minutes, step_minutes=step_minutes)


# -------------------------------------------------
# Bookings
# -------------------------------------------------
def add_booking_with_items(company_id: int, customer_name: str, phone: str, date: str, time: str,
                           items: list[dict]) -> int:
    """
    items = [{'service_id': 12, 'name': 'Pedicure Basic', 'price': 28.0, 'duration': 30}, ...]
    Slaat een snapshot van de items op zodat latere naams-/prijswijzigingen het verleden niet beïnvloeden.
    """
    total = sum(float(i.get("price", 0) or 0) for i in items)
    created_at = datetime.now().isoformat()

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO bookings (company_id, name, phone, date, time, total_price, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (company_id, customer_name, phone, date, time, total, created_at))
    booking_id = c.lastrowid

    for it in items:
        c.execute("""
            INSERT INTO booking_items (booking_id, service_id, name, price, duration)
            VALUES (?,?,?,?,?)
        """, (
            booking_id,
            it.get("service_id"),
            it.get("name"),
            float(it.get("price", 0) or 0),
            int(it.get("duration", 0) or 0),
        ))

    conn.commit()
    conn.close()
    return booking_id


def get_bookings(company_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT * FROM bookings WHERE company_id = ? ORDER BY date DESC, time DESC, id DESC",
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


def get_bookings_overview(company_id: int) -> pd.DataFrame:
    """
    Overzicht met samengevoegde items. COALESCE voor backwards-compat:
    gebruikt bi.name als die bestaat, anders services.name (oude data).
    """
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("""
        SELECT 
            b.id,
            b.name        AS customer_name,
            b.phone,
            b.date,
            b.time,
            ROUND(b.total_price, 2) AS total_price,
            GROUP_CONCAT(COALESCE(bi.name, s.name), ', ') AS items
        FROM bookings b
        LEFT JOIN booking_items bi ON bi.booking_id = b.id
        LEFT JOIN services s       ON s.id = bi.service_id
        WHERE b.company_id = ?
        GROUP BY b.id
        ORDER BY b.date DESC, b.time DESC, b.id DESC
    """, conn, params=(company_id,))
    conn.close()
    return df


# -------------------------------------------------
# Reminder settings (CRUD)
# -------------------------------------------------
def get_reminder_settings(company_id: int) -> dict:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM reminder_settings WHERE company_id = ?", (company_id,))
    row = c.fetchone()
    if not row:
        # standaard record aanmaken
        c.execute("""
            INSERT INTO reminder_settings (company_id, enabled, sms_enabled, whatsapp_enabled,
                                           days_before, send_time, same_day_enabled, same_day_minutes_before, tz)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (company_id, 0, 1, 0, 1, "09:00", 0, 60, "Europe/Brussels"))
        conn.commit()
        c.execute("SELECT * FROM reminder_settings WHERE company_id = ?", (company_id,))
        row = c.fetchone()

    # kolomnamen ophalen voor nette dict
    cols = [d[0] for d in c.description]
    conn.close()
    return dict(zip(cols, row))


def upsert_reminder_settings(
    company_id: int,
    enabled: int,
    sms_enabled: int,
    whatsapp_enabled: int,
    days_before: int,
    send_time: str,
    same_day_enabled: int,
    same_day_minutes_before: int,
    tz: str,
    template_day_before_sms: str = None,
    template_same_day_sms: str = None,
    template_day_before_wa: str = None,
    template_same_day_wa: str = None,
):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # bestaat record?
    c.execute("SELECT id FROM reminder_settings WHERE company_id = ?", (company_id,))
    row = c.fetchone()
    if row:
        c.execute("""
            UPDATE reminder_settings
               SET enabled=?, sms_enabled=?, whatsapp_enabled=?, days_before=?, send_time=?,
                   same_day_enabled=?, same_day_minutes_before=?, tz=?,
                   template_day_before_sms=?, template_same_day_sms=?,
                   template_day_before_wa=?,  template_same_day_wa=?
             WHERE company_id=?
        """, (enabled, sms_enabled, whatsapp_enabled, days_before, send_time,
              same_day_enabled, same_day_minutes_before, tz,
              template_day_before_sms, template_same_day_sms,
              template_day_before_wa, template_same_day_wa,
              company_id))
    else:
        c.execute("""
            INSERT INTO reminder_settings
                (company_id, enabled, sms_enabled, whatsapp_enabled, days_before, send_time,
                 same_day_enabled, same_day_minutes_before, tz,
                 template_day_before_sms, template_same_day_sms,
                 template_day_before_wa, template_same_day_wa)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (company_id, enabled, sms_enabled, whatsapp_enabled, days_before, send_time,
              same_day_enabled, same_day_minutes_before, tz,
              template_day_before_sms, template_same_day_sms,
              template_day_before_wa, template_same_day_wa))
    conn.commit()
    conn.close()
