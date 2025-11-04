import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

# --- Pad en map ---
DB_NAME = "data/bookings.db"
os.makedirs("data", exist_ok=True)


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

    # Categorieën met optionele beschrijving (per bedrijf)
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

    # Diensten
    c.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT,
            price REAL,
            duration INTEGER,
            category TEXT DEFAULT 'Algemeen',
            description TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # Beschikbaarheid
    c.execute("""
        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            day TEXT,              -- Maandag, Dinsdag, ...
            start_time TEXT,       -- HH:MM
            end_time TEXT,         -- HH:MM
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # Boeking + items
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT,
            phone TEXT,
            date TEXT,             -- YYYY-MM-DD
            time TEXT,             -- HH:MM
            total_price REAL DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

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

    # Herinnering-instellingen (SMS/WhatsApp)
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminder_settings (
            company_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,                 -- globale schakelaar
            sms_enabled INTEGER DEFAULT 1,             -- kanaal: sms
            whatsapp_enabled INTEGER DEFAULT 0,        -- kanaal: whatsapp
            days_before INTEGER DEFAULT 1,             -- aantal dagen vóór
            send_time TEXT DEFAULT '09:00',            -- HH:MM, lokale tz
            same_day_enabled INTEGER DEFAULT 0,        -- 2e herinnering op dezelfde dag
            same_day_minutes_before INTEGER DEFAULT 120,
            tz TEXT DEFAULT 'Europe/Brussels',
            template_day_before_sms TEXT DEFAULT 'Herinnering: je afspraak bij {company} op {date} om {time}.',
            template_same_day_sms  TEXT DEFAULT 'Tot straks! Je afspraak is om {time} bij {company}.',
            template_day_before_wa  TEXT DEFAULT 'Herinnering (WhatsApp): {company} – {date} {time}.',
            template_same_day_wa   TEXT DEFAULT 'WhatsApp: je afspraak is om {time} bij {company}.',
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    conn.commit()
    conn.close()


# ---------- Companies ----------
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
    row = c.fetchone()
    conn.close()
    return row


def update_company_paid(company_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE companies SET paid = 1 WHERE id = ?", (company_id,))
    conn.commit()
    conn.close()


def is_company_paid(company_id) -> int:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT paid FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


# ---------- Categories ----------
def upsert_category(company_id: int, name: str, description: str = ""):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO categories (company_id, name, description)
        VALUES (?, ?, ?)
        ON CONFLICT(company_id, name) DO UPDATE SET description = excluded.description
    """, (company_id, name.strip(), description.strip()))
    conn.commit()
    conn.close()


def get_categories(company_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT id, name, description FROM categories WHERE company_id = ? ORDER BY name ASC",
        conn, params=(company_id,))
    conn.close()
    return df


def get_category_description(company_id: int, name: str) -> str:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT description FROM categories WHERE company_id = ? AND name = ?",
              (company_id, name))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""


# ---------- Services ----------
def add_service(company_id, name, price, duration, category="Algemeen", description=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO services (company_id, name, price, duration, category, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (company_id, name, price, duration, category, description))
    conn.commit()
    conn.close()


def update_service(service_id: int, company_id: int, name: str, price: float,
                   duration: int, category: str, description: str | None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        UPDATE services
           SET name=?, price=?, duration=?, category=?, description=?
         WHERE id=? AND company_id=?
    """, (name, price, duration, category, description, service_id, company_id))
    conn.commit()
    conn.close()


def delete_service(service_id: int, company_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM services WHERE id=? AND company_id=?", (service_id, company_id))
    conn.commit()
    conn.close()


def get_services(company_id) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT id, name, price, duration, category, description FROM services WHERE company_id = ? ORDER BY category, name",
        conn, params=(company_id,))
    conn.close()
    return df


# ---------- Availability ----------
def add_availability(company_id, day, start_time, end_time):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO availability (company_id, day, start_time, end_time)
        VALUES (?, ?, ?, ?)
    """, (company_id, day, start_time, end_time))
    conn.commit()
    conn.close()


def get_availability(company_id) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("""
        SELECT id, day, start_time, end_time
          FROM availability
         WHERE company_id = ?
         ORDER BY
           CASE day
             WHEN 'Maandag' THEN 1 WHEN 'Dinsdag' THEN 2 WHEN 'Woensdag' THEN 3
             WHEN 'Donderdag' THEN 4 WHEN 'Vrijdag' THEN 5 WHEN 'Zaterdag' THEN 6
             WHEN 'Zondag' THEN 7 ELSE 8
           END
    """, conn, params=(company_id,))
    conn.close()
    return df


# Weekdag mapping zonder locale() (stabiel op Streamlit Cloud)
_DUTCH_DAYS = ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"]

def _weekday_name(date_str: str) -> str:
    ts = pd.Timestamp(date_str)
    return _DUTCH_DAYS[ts.dayofweek]


def get_available_slots(company_id, date: str) -> list[str]:
    """30-min slots gebaseerd op eerste regel availability voor die dag (simpel)."""
    avail = get_availability(company_id)
    if avail.empty:
        return []
    day = _weekday_name(date)
    avail_day = avail[avail["day"] == day]
    if avail_day.empty:
        return []
    row = avail_day.iloc[0]
    start = pd.Timestamp(f"{date} {row['start_time']}")
    end = pd.Timestamp(f"{date} {row['end_time']}")
    slots = []
    cur = start
    while cur < end:
        slots.append(cur.strftime("%H:%M"))
        cur += pd.Timedelta(minutes=30)
    return slots


def get_available_slots_for_duration(company_id, date: str, total_duration_minutes: int) -> list[str]:
    """Returneer starttijden waar het totale pakket in past."""
    avail = get_availability(company_id)
    if avail.empty:
        return []
    day = _weekday_name(date)
    avail_day = avail[avail["day"] == day]
    if avail_day.empty:
        return []
    row = avail_day.iloc[0]
    start = pd.Timestamp(f"{date} {row['start_time']}")
    end = pd.Timestamp(f"{date} {row['end_time']}")
    slots = []
    cur = start
    while cur + pd.Timedelta(minutes=total_duration_minutes) <= end:
        slots.append(cur.strftime("%H:%M"))
        cur += pd.Timedelta(minutes=15)  # fijner raster voor pakketten
    return slots


# ---------- Bookings ----------
def add_booking_with_items(company_id: int, name: str, phone: str,
                           service_ids: list[int], date: str, time: str) -> int:
    """Slaat boeking + items op, berekent total_price."""
    if not service_ids:
        raise ValueError("Geen diensten geselecteerd")
    services = get_services(company_id)
    pick = services[services["id"].isin(service_ids)]
    total_price = float(pick["price"].sum()) if not pick.empty else 0.0

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    c.execute("""
        INSERT INTO bookings (company_id, name, phone, date, time, total_price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (company_id, name, phone, date, time, total_price, created_at))
    booking_id = c.lastrowid

    for _, s in pick.iterrows():
        c.execute("""
            INSERT INTO booking_items (booking_id, service_id, name, price, duration)
            VALUES (?, ?, ?, ?, ?)
        """, (booking_id, int(s["id"]), s["name"], float(s["price"]), int(s["duration"])))

    conn.commit()
    conn.close()
    return booking_id


def get_bookings_overview(company_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("""
        SELECT b.id, b.name, b.phone, b.date, b.time, b.total_price,
               GROUP_CONCAT(bi.name, ', ') AS items
          FROM bookings b
          LEFT JOIN booking_items bi ON bi.booking_id = b.id
         WHERE b.company_id = ?
         GROUP BY b.id
         ORDER BY b.date DESC, b.time DESC, b.id DESC
    """, conn, params=(company_id,))
    conn.close()
    return df


# ---------- Reminder settings ----------
def get_reminder_settings(company_id: int) -> dict:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT enabled, sms_enabled, whatsapp_enabled, days_before, send_time,
               same_day_enabled, same_day_minutes_before, tz,
               template_day_before_sms, template_same_day_sms,
               template_day_before_wa,  template_same_day_wa
          FROM reminder_settings WHERE company_id=?
    """, (company_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return {
            "enabled": 0, "sms_enabled": 1, "whatsapp_enabled": 0,
            "days_before": 1, "send_time": "09:00",
            "same_day_enabled": 0, "same_day_minutes_before": 120,
            "tz": "Europe/Brussels",
            "template_day_before_sms": "Herinnering: je afspraak bij {company} op {date} om {time}.",
            "template_same_day_sms":  "Tot straks! Je afspraak is om {time} bij {company}.",
            "template_day_before_wa":  "Herinnering (WhatsApp): {company} – {date} {time}.",
            "template_same_day_wa":   "WhatsApp: je afspraak is om {time} bij {company}.",
        }

    keys = [
        "enabled", "sms_enabled", "whatsapp_enabled", "days_before", "send_time",
        "same_day_enabled", "same_day_minutes_before", "tz",
        "template_day_before_sms", "template_same_day_sms",
        "template_day_before_wa",  "template_same_day_wa"
    ]
    return dict(zip(keys, row))


def save_reminder_settings(
    company_id: int, enabled: int, sms_enabled: int, whatsapp_enabled: int,
    days_before: int, send_time: str, same_day_enabled: int,
    same_day_minutes_before: int, tz: str,
    template_day_before_sms: str, template_same_day_sms: str,
    template_day_before_wa: str, template_same_day_wa: str
):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO reminder_settings (
            company_id, enabled, sms_enabled, whatsapp_enabled,
            days_before, send_time, same_day_enabled, same_day_minutes_before, tz,
            template_day_before_sms, template_same_day_sms,
            template_day_before_wa,  template_same_day_wa
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(company_id) DO UPDATE SET
            enabled=excluded.enabled,
            sms_enabled=excluded.sms_enabled,
            whatsapp_enabled=excluded.whatsapp_enabled,
            days_before=excluded.days_before,
            send_time=excluded.send_time,
            same_day_enabled=excluded.same_day_enabled,
            same_day_minutes_before=excluded.same_day_minutes_before,
            tz=excluded.tz,
            template_day_before_sms=excluded.template_day_before_sms,
            template_same_day_sms=excluded.template_same_day_sms,
            template_day_before_wa=excluded.template_day_before_wa,
            template_same_day_wa=excluded.template_same_day_wa
    """, (
        company_id, enabled, sms_enabled, whatsapp_enabled,
        days_before, send_time, same_day_enabled, same_day_minutes_before, tz,
        template_day_before_sms, template_same_day_sms,
        template_day_before_wa,  template_same_day_wa
    ))
    conn.commit()
    conn.close()
