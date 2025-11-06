import os
import sqlite3
import pandas as pd
from datetime import datetime, time as dtime, timedelta

# =================================================
# Pad + DB-bestand
# =================================================
os.makedirs("data", exist_ok=True)
DB_NAME = "data/bookings.db"

def get_connection() -> sqlite3.Connection:
    """
    Maak een SQLite-verbinding met verstandige PRAGMA's.
    - foreign_keys ON: relationele integriteit
    - journal_mode WAL + synchronous NORMAL: snellere writes
    - busy_timeout: wacht even i.p.v. meteen "database is locked"
    """
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")  # 5s
    return conn

# =================================================
# Helper: migraties voor oudere DB's
# =================================================
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

def _ensure_services_is_active_column(conn: sqlite3.Connection):
    """
    Zorgt dat de kolom services.is_active bestaat (1 = zichtbaar voor klanten).
    """
    c = conn.cursor()
    c.execute("PRAGMA table_info(services)")
    cols = {row[1] for row in c.fetchall()}
    if "is_active" not in cols:
        c.execute("ALTER TABLE services ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    conn.commit()

def _ensure_indexes(conn: sqlite3.Connection):
    """
    Maak nuttige indexes aan (IF NOT EXISTS) voor performance.
    """
    c = conn.cursor()
    c.execute("CREATE INDEX IF NOT EXISTS idx_categories_company      ON categories(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_services_company        ON services(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_services_category       ON services(category)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_availability_company    ON availability(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_availability_companyday ON availability(company_id, day)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_company_date   ON bookings(company_id, date, time)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_booking_items_booking   ON booking_items(booking_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_booking_items_service   ON booking_items(service_id)")
    conn.commit()

# =================================================
# DB init
# =================================================
def init_db():
    """
    Idempotente initialisatie:
    - maakt tabellen indien nodig
    - voert migraties uit (snapshot-kolommen, is_active)
    - zet indexes
    """
    conn = get_connection()
    c = conn.cursor()

    # Bedrijven
    c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            email      TEXT    UNIQUE,
            password   TEXT,
            paid       INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    # Categorieën
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name       TEXT,
            description TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Diensten
    c.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER            NOT NULL,
            name       TEXT               NOT NULL,
            price      REAL               NOT NULL DEFAULT 0 CHECK (price >= 0),
            duration   INTEGER            NOT NULL DEFAULT 0 CHECK (duration >= 0),
            category   TEXT,
            description TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Beschikbaarheid
    c.execute("""
        CREATE TABLE IF NOT EXISTS availability (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            day        TEXT    NOT NULL,   -- bv. 'Maandag'
            start_time TEXT    NOT NULL,   -- 'HH:MM'
            end_time   TEXT    NOT NULL,   -- 'HH:MM'
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Boekingen (header)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER NOT NULL,
            name        TEXT,
            phone       TEXT,
            date        TEXT    NOT NULL,  -- YYYY-MM-DD
            time        TEXT    NOT NULL,  -- HH:MM starttijd
            total_price REAL    NOT NULL DEFAULT 0,
            created_at  TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Boekingsitems (details)
    c.execute("""
        CREATE TABLE IF NOT EXISTS booking_items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            service_id INTEGER,
            name       TEXT,
            price      REAL,
            duration   INTEGER,
            FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE SET NULL
        )
    """)

    # Herinnering-instellingen
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminder_settings (
            id                         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id                 INTEGER UNIQUE,
            enabled                    INTEGER DEFAULT 0,
            sms_enabled                INTEGER DEFAULT 1,
            whatsapp_enabled           INTEGER DEFAULT 0,
            days_before                INTEGER DEFAULT 1,
            send_time                  TEXT    DEFAULT '09:00',
            same_day_enabled           INTEGER DEFAULT 0,
            same_day_minutes_before    INTEGER DEFAULT 60,
            tz                         TEXT    DEFAULT 'Europe/Brussels',
            template_day_before_sms    TEXT,
            template_same_day_sms      TEXT,
            template_day_before_wa     TEXT,
            template_same_day_wa       TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """)

    # Migraties & indexes
    _ensure_booking_items_snapshot_columns(conn)
    _ensure_services_is_active_column(conn)
    _ensure_indexes(conn)

    conn.commit()
    conn.close()

# =================================================
# Companies
# =================================================
def add_company(name: str, email: str, password: str) -> int:
    """Voegt een nieuw bedrijf toe aan de database en geeft het ID terug."""
    conn = get_connection()
    try:
        c = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        c.execute(
            "INSERT INTO companies (name, email, password, created_at) VALUES (?,?,?,?)",
            (name, email, password, created_at),
        )
        conn.commit()
        return c.lastrowid
    except Exception as e:
        print(f"❌ Fout bij toevoegen van bedrijf: {e}")
        return -1
    finally:
        conn.close()

def get_company_by_email(email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return row

def is_company_paid(company_id: int) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT paid FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_company_paid(company_id: int, paid: int = 1):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE companies SET paid = ? WHERE id = ?", (paid, company_id))
    conn.commit()
    conn.close()

def activate_company(company_id: int):
    """Markeer bedrijf als betaald/actief."""
    update_company_paid(company_id, 1)

def get_company_name_by_id(company_id: int) -> str:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else f"bedrijf #{company_id}"

def get_company(company_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_company_profile(
    company_id: int,
    name: str,
    email: str,
    password: str | None = None
) -> bool:
    """Wijzig naam/e-mail; wachtwoord alleen als meegegeven."""
    conn = get_connection()
    try:
        c = conn.cursor()
        if password:
            c.execute(
                "UPDATE companies SET name=?, email=?, password=? WHERE id=?",
                (name, email, password, company_id),
            )
        else:
            c.execute(
                "UPDATE companies SET name=?, email=? WHERE id=?",
                (name, email, company_id),
            )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

# =================================================
# Categories
# =================================================
def add_category(company_id: int, name: str, description: str = ""):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO categories (company_id, name, description) VALUES (?,?,?)",
        (company_id, name, description),
    )
    conn.commit()
    conn.close()

def upsert_category(company_id: int, name: str, description: str = ""):
    """
    Voeg toe als hij niet bestaat; anders update beschrijving.
    (uniekheid per company_id + name afdwingen doen we applicatief)
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM categories WHERE company_id = ? AND name = ?",
        (company_id, name),
    )
    row = c.fetchone()
    if row:
        c.execute(
            "UPDATE categories SET description=? WHERE id=?",
            (description, row[0]),
        )
    else:
        c.execute(
            "INSERT INTO categories (company_id, name, description) VALUES (?,?,?)",
            (company_id, name, description),
        )
    conn.commit()
    conn.close()

def get_categories(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM categories WHERE company_id = ? ORDER BY name ASC",
        conn, params=(company_id,)
    )
    conn.close()
    return df

def update_category(category_id: int, name: str, description: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE categories SET name=?, description=? WHERE id=?",
        (name, description, category_id),
    )
    conn.commit()
    conn.close()

def delete_category(category_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()

# =================================================
# Services
# =================================================
def add_service(company_id: int, name: str, price: float, duration: int, category: str, description: str = ""):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO services (company_id, name, price, duration, category, description) VALUES (?,?,?,?,?,?)",
        (company_id, name, price, duration, category, description),
    )
    conn.commit()
    conn.close()

def get_services(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM services WHERE company_id = ? ORDER BY COALESCE(category,'Algemeen'), name",
        conn, params=(company_id,)
    )
    conn.close()
    return df

def update_service(service_id: int, name: str, price: float, duration: int, category: str, description: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE services SET name=?, price=?, duration=?, category=?, description=? WHERE id=?",
        (name, price, duration, category, description, service_id),
    )
    conn.commit()
    conn.close()

def delete_service(service_id: int):
    """Verwijder service; bestaande booking_items blijven als snapshot bestaan."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM services WHERE id = ?", (service_id,))
    conn.commit()
    conn.close()

def set_service_active(service_id: int, is_active: bool):
    """Activeer/deactiveer dienst voor klantenweergave (is_active: 1/0)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE services SET is_active=? WHERE id=?", (1 if is_active else 0, service_id))
    conn.commit()
    conn.close()

def get_public_services(company_id: int) -> pd.DataFrame:
    """Alleen diensten die zichtbaar zijn voor klanten (is_active = 1)."""
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT id, name, price, duration, category, description
        FROM services
        WHERE company_id = ? AND COALESCE(is_active, 1) = 1
        ORDER BY COALESCE(category, 'Algemeen'), name
        """,
        conn,
        params=(company_id,),
    )
    conn.close()
    return df

# =================================================
# Availability
# =================================================
def add_availability(company_id: int, day: str, start_time: str, end_time: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO availability (company_id, day, start_time, end_time) VALUES (?,?,?,?)",
        (company_id, day, start_time, end_time),
    )
    conn.commit()
    conn.close()

def get_availability(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM availability WHERE company_id = ?",
        conn, params=(company_id,)
    )
    conn.close()
    return df

# =================================================
# Slots helpers (met overlapcontrole)
# =================================================
_DUTCH_DAYS = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]

def _dayname_nl(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    return _DUTCH_DAYS[dt.weekday()]

def _to_dt(date_str: str, hhmm: str) -> datetime:
    return datetime.combine(
        datetime.strptime(date_str, "%Y-%m-%d").date(),
        dtime.fromisoformat(hhmm)
    )

def _get_booked_intervals(company_id: int, date: str) -> list[tuple[datetime, datetime]]:
    """
    Haal reeds geboekte intervallen op voor een datum, gebaseerd op:
    bookings (start 'time') + som(duration) uit booking_items.
    """
    conn = get_connection()
    # total_duration per booking_id
    dur_df = pd.read_sql_query(
        """
        SELECT b.id AS booking_id, b.time AS start_time,
               COALESCE(SUM(bi.duration), 0) AS total_minutes
        FROM bookings b
        LEFT JOIN booking_items bi ON bi.booking_id = b.id
        WHERE b.company_id = ? AND b.date = ?
        GROUP BY b.id
        """,
        conn, params=(company_id, date)
    )
    conn.close()

    intervals: list[tuple[datetime, datetime]] = []
    if dur_df.empty:
        return intervals

    for _, r in dur_df.iterrows():
        try:
            start_dt = _to_dt(date, r["start_time"])
            total_min = int(r["total_minutes"] or 0)
            end_dt = start_dt + timedelta(minutes=total_min)
            intervals.append((start_dt, end_dt))
        except Exception:
            continue
    return intervals

def get_available_slots(company_id: int, date: str, duration_minutes: int = 30, step_minutes: int = 5) -> list[str]:
    """
    Genereer slots binnen de beschikbaarheden van de gekozen dag.
    Houdt rekening met reeds geboekte afspraken (geen overlap).
    """
    avail = get_availability(company_id)
    if avail.empty:
        return []

    dayname = _dayname_nl(date)
    day_rows = avail[avail["day"] == dayname]
    if day_rows.empty:
        return []

    booked = _get_booked_intervals(company_id, date)

    def overlaps(s: datetime, e: datetime) -> bool:
        for bs, be in booked:
            # echte overlap: s<be en bs<e
            if s < be and bs < e:
                return True
        return False

    slots = []
    dur = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=step_minutes)

    for _, row in day_rows.iterrows():
        start_dt = _to_dt(date, row["start_time"])
        end_dt = _to_dt(date, row["end_time"])
        cursor = start_dt
        while cursor + dur <= end_dt:
            nxt = cursor + dur
            if not overlaps(cursor, nxt):
                slots.append(cursor.strftime("%H:%M"))
            cursor += step

    return sorted(slots)

def get_available_slots_for_duration(company_id: int, date: str, total_minutes: int, step_minutes: int = 5) -> list[str]:
    return get_available_slots(company_id, date, duration_minutes=total_minutes, step_minutes=step_minutes)

# =================================================
# Bookings
# =================================================
def add_booking_with_items(company_id: int, customer_name: str, phone: str, date: str, time: str,
                           items: list[dict]) -> int:
    """
    items = [{'service_id': 12, 'name': 'Pedicure Basic', 'price': 28.0, 'duration': 30}, ...]
    Snapshot wordt opgeslagen (name/price/duration) zodat historische data klopt bij latere prijswijzigingen.
    Overlap-veilig: doet een snelle overlapcheck binnen hetzelfde transactioneel venster.
    """
    total = sum(float(i.get("price", 0) or 0) for i in items)
    created_at = datetime.utcnow().isoformat()
    total_minutes = sum(int(i.get("duration", 0) or 0) for i in items)

    # bereken eindtijd t.b.v. overlapcontrole (best effort)
    start_dt = _to_dt(date, time)
    end_dt = start_dt + timedelta(minutes=total_minutes)

    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("BEGIN IMMEDIATE")  # lock snel om race conditions te verkleinen

        # Overlap-check binnen de DB-verbinding
        for s, e in _get_booked_intervals(company_id, date):
            if start_dt < e and s < end_dt:
                raise ValueError("Dit tijdslot overlapt met een bestaande afspraak.")

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
        return booking_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_bookings(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM bookings WHERE company_id = ? ORDER BY date DESC, time DESC, id DESC",
        conn, params=(company_id,)
    )
    conn.close()
    return df

def get_bookings_overview(company_id: int) -> pd.DataFrame:
    """
    Overzicht met samengevoegde items. COALESCE: gebruik bi.name (snapshot) of fallback naar services.name (oude data).
    """
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT 
            b.id,
            b.name        AS customer_name,
            b.phone,
            b.date,
            b.time,
            ROUND(b.total_price, 2) AS total_price,
            COALESCE(SUM(bi.duration), 0) AS total_minutes,
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

# =================================================
# Reminder settings (CRUD)
# =================================================
def get_reminder_settings(company_id: int) -> dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM reminder_settings WHERE company_id = ?", (company_id,))
    row = c.fetchone()
    if not row:
        c.execute("""
            INSERT INTO reminder_settings (company_id, enabled, sms_enabled, whatsapp_enabled,
                                           days_before, send_time, same_day_enabled, same_day_minutes_before, tz)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (company_id, 0, 1, 0, 1, "09:00", 0, 60, "Europe/Brussels"))
        conn.commit()
        c.execute("SELECT * FROM reminder_settings WHERE company_id = ?", (company_id,))
        row = c.fetchone()

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
    template_day_before_sms: str | None = None,
    template_same_day_sms: str | None = None,
    template_day_before_wa: str | None = None,
    template_same_day_wa: str | None = None,
):
    conn = get_connection()
    c = conn.cursor()

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
