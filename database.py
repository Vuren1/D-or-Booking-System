import os
import re
import sqlite3
from datetime import datetime, date as ddate, time as dtime, timedelta
from typing import Iterable, List, Optional, Tuple

import pandas as pd

# Zorg dat data map bestaat
os.makedirs("data", exist_ok=True)
DB_NAME = "data/bookings.db"


# =============================
# DB helpers
# =============================
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def _slugify(name: str) -> str:
    if not name:
        return "bedrijf"
    value = name.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "bedrijf"


# =============================
# INIT / MIGRATIES
# =============================
def init_db():
    conn = get_connection()
    c = conn.cursor()

    # ---------------- Companies ----------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            email      TEXT    UNIQUE,
            password   TEXT,
            paid       INTEGER DEFAULT 0,
            created_at TEXT,
            slug       TEXT    UNIQUE,
            logo_path  TEXT
        )
        """
    )
    # migreer kolommen indien ontbreken
    for ddl in [
        "ALTER TABLE companies ADD COLUMN slug TEXT UNIQUE",
        "ALTER TABLE companies ADD COLUMN logo_path TEXT",
    ]:
        try:
            c.execute(ddl)
        except Exception:
            pass

    # Slugs invullen voor bestaande bedrijven
    try:
        c.execute("SELECT id, name FROM companies WHERE slug IS NULL OR slug = ''")
        for row in c.fetchall():
            cid, nm = int(row["id"]), str(row["name"])
            base = _slugify(nm)
            slug = base
            i = 1
            while True:
                c.execute("SELECT 1 FROM companies WHERE slug=?", (slug,))
                if not c.fetchone():
                    break
                i += 1
                slug = f"{base}-{i}"
            c.execute("UPDATE companies SET slug=? WHERE id=?", (slug, cid))
    except Exception:
        pass

    # ---------------- Categories ----------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER NOT NULL,
            name        TEXT NOT NULL,
            description TEXT,
            UNIQUE(company_id, name),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """
    )

    # ---------------- Services ----------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS services (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER NOT NULL,
            name        TEXT NOT NULL,
            price       REAL NOT NULL DEFAULT 0,
            duration    INTEGER NOT NULL DEFAULT 0,
            category    TEXT,
            description TEXT,
            is_active   INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """
    )

    # ---------------- Availability ----------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS availability (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER NOT NULL,
            day         TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """
    )

    # ---------------- Bookings ----------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER NOT NULL,
            customer    TEXT,
            date        TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            total_price REAL NOT NULL DEFAULT 0,
            status      TEXT NOT NULL DEFAULT 'scheduled',
            created_at  TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """
    )
    # status toevoegen bij oudere db
    try:
        cols = {row["name"] for row in c.execute("PRAGMA table_info(bookings)")}
        if "status" not in cols:
            c.execute(
                "ALTER TABLE bookings ADD COLUMN status TEXT NOT NULL DEFAULT 'scheduled'"
            )
    except Exception:
        pass

    # ---------------- Booking items ----------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS booking_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id  INTEGER NOT NULL,
            service_id  INTEGER,
            name        TEXT,
            price       REAL,
            duration    INTEGER,
            FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
        )
        """
    )

    # ---------------- Reminder settings ----------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS reminder_settings (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id         INTEGER NOT NULL UNIQUE,
            active             INTEGER NOT NULL DEFAULT 0,

            rem1_days_before   INTEGER NOT NULL DEFAULT 1,
            rem1_time          TEXT    NOT NULL DEFAULT '09:00',
            rem1_sms           INTEGER NOT NULL DEFAULT 0,
            rem1_whatsapp      INTEGER NOT NULL DEFAULT 0,
            rem1_email         INTEGER NOT NULL DEFAULT 0,
            rem1_message_sms        TEXT,
            rem1_message_whatsapp   TEXT,
            rem1_message_email      TEXT,

            rem2_minutes_before INTEGER NOT NULL DEFAULT 60,
            rem2_sms            INTEGER NOT NULL DEFAULT 0,
            rem2_whatsapp       INTEGER NOT NULL DEFAULT 0,
            rem2_email          INTEGER NOT NULL DEFAULT 0,
            rem2_message_sms        TEXT,
            rem2_message_whatsapp   TEXT,
            rem2_message_email      TEXT,

            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """
    )

    # kolommen toevoegen indien oude versie
    try:
        rcols = {row["name"] for row in c.execute("PRAGMA table_info(reminder_settings)")}
    except sqlite3.OperationalError:
        rcols = set()

    def add_rem_col(name: str, ddl: str):
        if name not in rcols:
            try:
                c.execute(ddl)
            except Exception:
                pass

    add_rem_col("rem1_days_before",
                "ALTER TABLE reminder_settings ADD COLUMN rem1_days_before INTEGER NOT NULL DEFAULT 1")
    add_rem_col("rem1_time",
                "ALTER TABLE reminder_settings ADD COLUMN rem1_time TEXT NOT NULL DEFAULT '09:00'")
    add_rem_col("rem1_sms",
                "ALTER TABLE reminder_settings ADD COLUMN rem1_sms INTEGER NOT NULL DEFAULT 0")
    add_rem_col("rem1_whatsapp",
                "ALTER TABLE reminder_settings ADD COLUMN rem1_whatsapp INTEGER NOT NULL DEFAULT 0")
    add_rem_col("rem1_email",
                "ALTER TABLE reminder_settings ADD COLUMN rem1_email INTEGER NOT NULL DEFAULT 0")
    add_rem_col("rem1_message_sms",
                "ALTER TABLE reminder_settings ADD COLUMN rem1_message_sms TEXT")
    add_rem_col("rem1_message_whatsapp",
                "ALTER TABLE reminder_settings ADD COLUMN rem1_message_whatsapp TEXT")
    add_rem_col("rem1_message_email",
                "ALTER TABLE reminder_settings ADD COLUMN rem1_message_email TEXT")
    add_rem_col("rem2_minutes_before",
                "ALTER TABLE reminder_settings ADD COLUMN rem2_minutes_before INTEGER NOT NULL DEFAULT 60")
    add_rem_col("rem2_sms",
                "ALTER TABLE reminder_settings ADD COLUMN rem2_sms INTEGER NOT NULL DEFAULT 0")
    add_rem_col("rem2_whatsapp",
                "ALTER TABLE reminder_settings ADD COLUMN rem2_whatsapp INTEGER NOT NULL DEFAULT 0")
    add_rem_col("rem2_email",
                "ALTER TABLE reminder_settings ADD COLUMN rem2_email INTEGER NOT NULL DEFAULT 0")
    add_rem_col("rem2_message_sms",
                "ALTER TABLE reminder_settings ADD COLUMN rem2_message_sms TEXT")
    add_rem_col("rem2_message_whatsapp",
                "ALTER TABLE reminder_settings ADD COLUMN rem2_message_whatsapp TEXT")
    add_rem_col("rem2_message_email",
                "ALTER TABLE reminder_settings ADD COLUMN rem2_message_email TEXT")

    # ---------------- Message balances (bundels & verbruik) ----------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS message_balances (
            company_id      INTEGER PRIMARY KEY,
            whatsapp_credits INTEGER NOT NULL DEFAULT 0,
            sms_credits      INTEGER NOT NULL DEFAULT 0,
            email_limit      INTEGER NOT NULL DEFAULT 1000,
            email_used       INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """
    )
    try:
        mcols = {row["name"] for row in c.execute("PRAGMA table_info(message_balances)")}
    except sqlite3.OperationalError:
        mcols = set()

    def add_mb_col(name: str, ddl: str):
        if name not in mcols:
            try:
                c.execute(ddl)
            except Exception:
                pass

    add_mb_col(
        "whatsapp_credits",
        "ALTER TABLE message_balances ADD COLUMN whatsapp_credits INTEGER NOT NULL DEFAULT 0",
    )
    add_mb_col(
        "sms_credits",
        "ALTER TABLE message_balances ADD COLUMN sms_credits INTEGER NOT NULL DEFAULT 0",
    )
    add_mb_col(
        "email_limit",
        "ALTER TABLE message_balances ADD COLUMN email_limit INTEGER NOT NULL DEFAULT 1000",
    )
    add_mb_col(
        "email_used",
        "ALTER TABLE message_balances ADD COLUMN email_used INTEGER NOT NULL DEFAULT 0",
    )

    conn.commit()
    conn.close()


# =============================
# COMPANIES
# =============================
def add_company(name: str, email: str, password: str) -> int:
    conn = get_connection()
    try:
        c = conn.cursor()
        created_at = datetime.utcnow().isoformat()

        base = _slugify(name)
        slug = base
        i = 1
        while True:
            c.execute("SELECT 1 FROM companies WHERE slug=?", (slug,))
            if not c.fetchone():
                break
            i += 1
            slug = f"{base}-{i}"

        c.execute(
            """
            INSERT INTO companies (name, email, password, paid, created_at, slug)
            VALUES (?,?,?,?,?,?)
            """,
            (name, email, password, 0, created_at, slug),
        )
        cid = c.lastrowid

        # message balance entry aanmaken
        c.execute(
            """
            INSERT OR IGNORE INTO message_balances (company_id)
            VALUES (?)
            """,
            (cid,),
        )

        conn.commit()
        return cid
    except Exception as e:
        print("add_company error:", e)
        return -1
    finally:
        conn.close()


def get_company(company_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE id=?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row


def get_company_by_email(email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE lower(email)=lower(?)", (email,))
    row = c.fetchone()
    conn.close()
    return row


def get_company_by_slug(slug: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM companies WHERE slug=?", (slug,))
    row = c.fetchone()
    conn.close()
    return row


def get_company_slug(company_id: int) -> Optional[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT slug FROM companies WHERE id=?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row["slug"] if row and row["slug"] else None


def get_company_name_by_id(company_id: int) -> Optional[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM companies WHERE id=?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row["name"] if row else None


def set_company_logo(company_id: int, logo_path: str) -> bool:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            "UPDATE companies SET logo_path=? WHERE id=?",
            (logo_path, company_id),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_company_logo(company_id: int) -> Optional[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT logo_path FROM companies WHERE id=?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row["logo_path"] if row and row["logo_path"] else None


def is_company_paid(company_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT paid FROM companies WHERE id=?", (company_id,))
    row = c.fetchone()
    conn.close()
    return bool(row and row["paid"])


def update_company_paid(company_id: int, paid: bool):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE companies SET paid=? WHERE id=?",
        (1 if paid else 0, company_id),
    )
    conn.commit()
    conn.close()


def activate_company(company_id: int):
    update_company_paid(company_id, True)


def update_company_profile(
    company_id: int, name: str, email: str, password: Optional[str] = None
) -> bool:
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


# =============================
# CATEGORIES
# =============================
def get_categories(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT id, name, description
        FROM categories
        WHERE company_id=?
        ORDER BY name
        """,
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


def add_category(company_id: int, name: str, description: str = "") -> int:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT OR IGNORE INTO categories (company_id, name, description)
            VALUES (?,?,?)
            """,
            (company_id, name, description),
        )
        conn.commit()
        c.execute(
            """
            SELECT id FROM categories
            WHERE company_id=? AND name=?
            """,
            (company_id, name),
        )
        row = c.fetchone()
        return int(row["id"]) if row else -1
    finally:
        conn.close()


def upsert_category(company_id: int, name: str, description: str = "") -> int:
    return add_category(company_id, name, description)


# =============================
# SERVICES
# =============================
def get_services(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT id, name, price, duration, category, description, is_active
        FROM services
        WHERE company_id=?
        ORDER BY COALESCE(category, ''), name
        """,
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


def add_service(
    company_id: int,
    name: str,
    price: float,
    duration: int,
    category: Optional[str] = None,
    description: str = "",
    is_active: bool = True,
) -> int:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO services (company_id, name, price, duration, category, description, is_active)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                company_id,
                name,
                price,
                duration,
                category,
                description,
                1 if is_active else 0,
            ),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def update_service(
    service_id: int,
    name: Optional[str] = None,
    price: Optional[float] = None,
    duration: Optional[int] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> bool:
    sets = []
    params: List = []
    if name is not None:
        sets.append("name=?")
        params.append(name)
    if price is not None:
        sets.append("price=?")
        params.append(price)
    if duration is not None:
        sets.append("duration=?")
        params.append(duration)
    if category is not None:
        sets.append("category=?")
        params.append(category)
    if description is not None:
        sets.append("description=?")
        params.append(description)
    if is_active is not None:
        sets.append("is_active=?")
        params.append(1 if is_active else 0)

    if not sets:
        return True

    params.append(service_id)
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            f"UPDATE services SET {', '.join(sets)} WHERE id=?",
            params,
        )
        conn.commit()
        return True
    finally:
        conn.close()


def delete_service(service_id: int) -> bool:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM services WHERE id=?", (service_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def set_service_active(service_id: int, active: bool) -> bool:
    return update_service(service_id, is_active=active)


def get_public_services(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT name, price, duration, category, description
        FROM services
        WHERE company_id=? AND is_active=1
        ORDER BY COALESCE(category, ''), name
        """,
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


# =============================
# AVAILABILITY
# =============================
_DUTCH_DAYS = [
    "Maandag",
    "Dinsdag",
    "Woensdag",
    "Donderdag",
    "Vrijdag",
    "Zaterdag",
    "Zondag",
]


def add_availability(
    company_id: int, day: str, start_time: dtime, end_time: dtime
) -> int:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO availability (company_id, day, start_time, end_time)
            VALUES (?,?,?,?)
            """,
            (
                company_id,
                day,
                start_time.strftime("%H:%M"),
                end_time.strftime("%H:%M"),
            ),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def get_availability(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT id, day, start_time, end_time
        FROM availability
        WHERE company_id=?
        ORDER BY
          CASE day
            WHEN 'Maandag' THEN 1 WHEN 'Dinsdag' THEN 2 WHEN 'Woensdag' THEN 3
            WHEN 'Donderdag' THEN 4 WHEN 'Vrijdag' THEN 5 WHEN 'Zaterdag' THEN 6
            WHEN 'Zondag' THEN 7 ELSE 8 END,
          start_time
        """,
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


# =============================
# TIME SLOTS (optioneel)
# =============================
def get_available_slots_for_duration(
    company_id: int,
    target_date: ddate,
    duration_minutes: int,
    step_minutes: int = 15,
) -> List[str]:
    weekday_idx = target_date.weekday()
    day_name = _DUTCH_DAYS[weekday_idx]

    avail = get_availability(company_id)
    avail = avail[avail["day"] == day_name]
    if avail.empty:
        return []

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT start_time, end_time
        FROM bookings
        WHERE company_id=? AND date=?
        """,
        (company_id, target_date.strftime("%Y-%m-%d")),
    )
    busy = [(r["start_time"], r["end_time"]) for r in c.fetchall()]
    conn.close()

    busy_ranges: List[Tuple[int, int]] = []
    for s, e in busy:
        st_m = int(s[:2]) * 60 + int(s[3:5])
        en_m = int(e[:2]) * 60 + int(e[3:5])
        busy_ranges.append((st_m, en_m))

    def is_free(start_m: int, end_m: int) -> bool:
        for bs, be in busy_ranges:
            if not (end_m <= bs or start_m >= be):
                return False
        return True

    slots: List[str] = []
    for _, row in avail.iterrows():
        start_m = int(row["start_time"][:2]) * 60 + int(row["start_time"][3:5])
        end_m = int(row["end_time"][:2]) * 60 + int(row["end_time"][3:5])

        cur = start_m
        while cur + duration_minutes <= end_m:
            if is_free(cur, cur + duration_minutes):
                hh = cur // 60
                mm = cur % 60
                slots.append(f"{hh:02d}:{mm:02d}")
            cur += step_minutes

    return slots


# =============================
# BOOKINGS
# =============================
def add_booking_with_items(
    company_id: int,
    customer: str,
    date_str: str,
    start_time: str,
    items: Iterable[dict],
) -> int:
    items = list(items)
    total_minutes = sum(int(i.get("duration", 0)) for i in items)
    total_price = sum(float(i.get("price", 0)) for i in items)

    st_h, st_m = map(int, start_time.split(":"))
    start_dt = datetime.strptime(f"{date_str} {st_h:02d}:{st_m:02d}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=total_minutes)
    end_time = end_dt.strftime("%H:%M")

    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO bookings (
                company_id, customer, date, start_time, end_time,
                total_price, status, created_at
            )
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                company_id,
                customer,
                date_str,
                start_time,
                end_time,
                total_price,
                "scheduled",
                datetime.utcnow().isoformat(),
            ),
        )
        bid = c.lastrowid

        for it in items:
            c.execute(
                """
                INSERT INTO booking_items (booking_id, service_id, name, price, duration)
                VALUES (?,?,?,?,?)
                """,
                (
                    bid,
                    it.get("service_id"),
                    it.get("name"),
                    it.get("price"),
                    it.get("duration"),
                ),
            )

        conn.commit()
        return bid
    finally:
        conn.close()


def get_bookings(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT id, customer, date, start_time, end_time, total_price, status
        FROM bookings
        WHERE company_id=?
        ORDER BY date DESC, start_time DESC
        """,
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


def get_bookings_overview(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            date,
            COUNT(*)           AS total_bookings,
            SUM(total_price)   AS revenue
        FROM bookings
        WHERE company_id=?
        GROUP BY date
        ORDER BY date DESC
        """,
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


def update_booking_status(
    company_id: int, booking_id: int, status: str
) -> bool:
    status = status.lower().strip()
    if status not in {"scheduled", "completed", "no_show", "cancelled"}:
        return False
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            UPDATE bookings
            SET status=?
            WHERE id=? AND company_id=?
            """,
            (status, booking_id, company_id),
        )
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


def get_status_overview(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT status, COUNT(*) AS count
        FROM bookings
        WHERE company_id=?
        GROUP BY status
        """,
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


def get_customer_stats(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            TRIM(customer) AS customer,
            COUNT(*)       AS total_bookings,
            SUM(total_price) AS total_revenue,
            MAX(date)      AS last_date
        FROM bookings
        WHERE company_id=?
          AND customer IS NOT NULL
          AND TRIM(customer) <> ''
        GROUP BY TRIM(customer)
        ORDER BY total_bookings DESC, last_date DESC
        """,
        conn,
        params=(company_id,),
    )
    conn.close()
    return df


# =============================
# REMINDER SETTINGS
# =============================
def get_reminder_settings(company_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            active,
            rem1_days_before,
            rem1_time,
            rem1_sms,
            rem1_whatsapp,
            rem1_email,
            rem1_message_sms,
            rem1_message_whatsapp,
            rem1_message_email,
            rem2_minutes_before,
            rem2_sms,
            rem2_whatsapp,
            rem2_email,
            rem2_message_sms,
            rem2_message_whatsapp,
            rem2_message_email
        FROM reminder_settings
        WHERE company_id=?
        """,
        conn,
        params=(company_id,),
    )
    conn.close()

    if df.empty:
        # standaard template
        df = pd.DataFrame(
            [
                dict(
                    active=0,
                    rem1_days_before=1,
                    rem1_time="09:00",
                    rem1_sms=0,
                    rem1_whatsapp=0,
                    rem1_email=1,
                    rem1_message_sms="Beste {klantnaam}, dit is een herinnering voor uw afspraak op {datum} om {tijd}.",
                    rem1_message_whatsapp="Beste {klantnaam}, we zien u graag op {datum} om {tijd}.",
                    rem1_message_email=(
                        "Beste {klantnaam},\n\n"
                        "Dit is een herinnering voor uw afspraak op {datum} om {tijd}.\n\n"
                        "Met vriendelijke groeten,\n{bedrijfsnaam}"
                    ),
                    rem2_minutes_before=60,
                    rem2_sms=0,
                    rem2_whatsapp=0,
                    rem2_email=0,
                    rem2_message_sms="Beste {klantnaam}, uw afspraak start om {tijd}. Tot zo!",
                    rem2_message_whatsapp="Hi {klantnaam}, uw afspraak begint om {tijd}. Tot zo!",
                    rem2_message_email=(
                        "Beste {klantnaam},\n\n"
                        "Uw afspraak start bijna, om {tijd}.\n\n"
                        "Met vriendelijke groeten,\n{bedrijfsnaam}"
                    ),
                )
            ]
        )

    defaults = {
        "active": 0,
        "rem1_days_before": 1,
        "rem1_time": "09:00",
        "rem1_sms": 0,
        "rem1_whatsapp": 0,
        "rem1_email": 0,
        "rem1_message_sms": "",
        "rem1_message_whatsapp": "",
        "rem1_message_email": "",
        "rem2_minutes_before": 60,
        "rem2_sms": 0,
        "rem2_whatsapp": 0,
        "rem2_email": 0,
        "rem2_message_sms": "",
        "rem2_message_whatsapp": "",
        "rem2_message_email": "",
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val
        df[col] = df[col].fillna(val)

    return df.iloc[[0]]


def upsert_reminder_settings(
    company_id: int,
    active: bool,
    rem1_days_before: int,
    rem1_time: str,
    rem1_sms: bool,
    rem1_whatsapp: bool,
    rem1_email: bool,
    rem1_message_sms: str,
    rem1_message_whatsapp: str,
    rem1_message_email: str,
    rem2_minutes_before: int,
    rem2_sms: bool,
    rem2_whatsapp: bool,
    rem2_email: bool,
    rem2_message_sms: str,
    rem2_message_whatsapp: str,
    rem2_message_email: str,
) -> bool:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO reminder_settings (
                company_id,
                active,
                rem1_days_before,
                rem1_time,
                rem1_sms,
                rem1_whatsapp,
                rem1_email,
                rem1_message_sms,
                rem1_message_whatsapp,
                rem1_message_email,
                rem2_minutes_before,
                rem2_sms,
                rem2_whatsapp,
                rem2_email,
                rem2_message_sms,
                rem2_message_whatsapp,
                rem2_message_email
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(company_id) DO UPDATE SET
                active                = excluded.active,
                rem1_days_before      = excluded.rem1_days_before,
                rem1_time             = excluded.rem1_time,
                rem1_sms              = excluded.rem1_sms,
                rem1_whatsapp         = excluded.rem1_whatsapp,
                rem1_email            = excluded.rem1_email,
                rem1_message_sms      = excluded.rem1_message_sms,
                rem1_message_whatsapp = excluded.rem1_message_whatsapp,
                rem1_message_email    = excluded.rem1_message_email,
                rem2_minutes_before   = excluded.rem2_minutes_before,
                rem2_sms              = excluded.rem2_sms,
                rem2_whatsapp         = excluded.rem2_whatsapp,
                rem2_email            = excluded.rem2_email,
                rem2_message_sms      = excluded.rem2_message_sms,
                rem2_message_whatsapp = excluded.rem2_message_whatsapp,
                rem2_message_email    = excluded.rem2_message_email
            """,
            (
                company_id,
                1 if active else 0,
                int(rem1_days_before),
                rem1_time,
                1 if rem1_sms else 0,
                1 if rem1_whatsapp else 0,
                1 if rem1_email else 0,
                rem1_message_sms,
                rem1_message_whatsapp,
                rem1_message_email,
                int(rem2_minutes_before),
                1 if rem2_sms else 0,
                1 if rem2_whatsapp else 0,
                1 if rem2_email else 0,
                rem2_message_sms,
                rem2_message_whatsapp,
                rem2_message_email,
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


# =============================
# MESSAGE BUNDLES & USAGE
# =============================
def ensure_message_balance(company_id: int):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT OR IGNORE INTO message_balances (company_id)
            VALUES (?)
            """,
            (company_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_message_balances(company_id: int) -> dict:
    ensure_message_balance(company_id)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT whatsapp_credits, sms_credits, email_limit, email_used
        FROM message_balances
        WHERE company_id=?
        """,
        (company_id,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return dict(
            whatsapp_credits=0,
            sms_credits=0,
            email_limit=1000,
            email_used=0,
        )
    return dict(row)


def add_whatsapp_credits(company_id: int, amount: int):
    ensure_message_balance(company_id)
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            UPDATE message_balances
            SET whatsapp_credits = whatsapp_credits + ?
            WHERE company_id=?
            """,
            (int(amount), company_id),
        )
        conn.commit()
    finally:
        conn.close()


def add_sms_credits(company_id: int, amount: int):
    ensure_message_balance(company_id)
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            UPDATE message_balances
            SET sms_credits = sms_credits + ?
            WHERE company_id=?
            """,
            (int(amount), company_id),
        )
        conn.commit()
    finally:
        conn.close()


def add_email_limit(company_id: int, extra_limit: int):
    ensure_message_balance(company_id)
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            UPDATE message_balances
            SET email_limit = email_limit + ?
            WHERE company_id=?
            """,
            (int(extra_limit), company_id),
        )
        conn.commit()
    finally:
        conn.close()


def register_message_usage(
    company_id: int, msg_type: str, count: int = 1
) -> bool:
    """
    Trek credits af (whatsapp/sms) of verhoog email_used.
    Return False als er onvoldoende tegoed is.
    Dit wordt door je scheduler / notificatie-service gebruikt.
    """
    ensure_message_balance(company_id)
    msg_type = msg_type.lower()
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT whatsapp_credits, sms_credits, email_limit, email_used
            FROM message_balances
            WHERE company_id=?
            """,
            (company_id,),
        )
        row = c.fetchone()
        if not row:
            return False
        wc = int(row["whatsapp_credits"])
        sc = int(row["sms_credits"])
        el = int(row["email_limit"])
        eu = int(row["email_used"])
        count = int(count)

        if msg_type == "whatsapp":
            if wc < count:
                return False
            c.execute(
                """
                UPDATE message_balances
                SET whatsapp_credits = whatsapp_credits - ?
                WHERE company_id=?
                """,
                (count, company_id),
            )
        elif msg_type == "sms":
            if sc < count:
                return False
            c.execute(
                """
                UPDATE message_balances
                SET sms_credits = sms_credits - ?
                WHERE company_id=?
                """,
                (count, company_id),
            )
        elif msg_type == "email":
            if eu + count > el:
                return False
            c.execute(
                """
                UPDATE message_balances
                SET email_used = email_used + ?
                WHERE company_id=?
                """,
                (count, company_id),
            )
        else:
            return False

        conn.commit()
        return True
    finally:
        conn.close()


def get_message_usage_summary(company_id: int) -> dict:
    """Gebruik voor UI: huidige credits + e-mail gebruik."""
    return get_message_balances(company_id)
