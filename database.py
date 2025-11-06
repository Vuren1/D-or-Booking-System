import os
import sqlite3
import re
import pandas as pd
from datetime import datetime, time as dtime, timedelta

# =================================================
# Pad + DB-bestand
# =================================================
os.makedirs("data", exist_ok=True)
DB_NAME = "data/bookings.db"


def _slugify(name: str) -> str:
    """Maak een nette slug op basis van de bedrijfsnaam."""
    if not name:
        return "bedrijf"
    value = name.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "bedrijf"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def init_db():
    """
    Maakt tabellen indien nodig + simpele migraties.
    """
    conn = get_connection()
    c = conn.cursor()

    # Bedrijven
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

    # Migraties voor bestaande DB's
    try:
        c.execute("ALTER TABLE companies ADD COLUMN slug TEXT UNIQUE")
    except Exception:
        pass

    try:
        c.execute("ALTER TABLE companies ADD COLUMN logo_path TEXT")
    except Exception:
        pass

    # Slugs vullen indien leeg
    try:
        c.execute(
            "SELECT id, name FROM companies WHERE slug IS NULL OR slug = ''"
        )
        rows = c.fetchall()
        for cid, name in rows:
            base = _slugify(name)
            slug = base
            i = 1
            while True:
                c.execute("SELECT 1 FROM companies WHERE slug = ?", (slug,))
                if not c.fetchone():
                    break
                i += 1
                slug = f"{base}-{i}"
            c.execute(
                "UPDATE companies SET slug=? WHERE id=?", (slug, cid)
            )
        conn.commit()
    except Exception:
        pass

    # Categorieën
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER NOT NULL,
            name        TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """
    )

    # Diensten
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS services (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name       TEXT NOT NULL,
            price      REAL NOT NULL DEFAULT 0,
            duration   INTEGER NOT NULL DEFAULT 0,
            category   TEXT,
            description TEXT,
            is_active  INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """
    )

    # Beschikbaarheid
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS availability (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            day        TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time   TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """
    )

    # Boekingen (header)
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
            created_at  TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """
    )

    # Boekingsregels
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

    # Reminder settings
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS reminder_settings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER NOT NULL,
            offset_hours INTEGER NOT NULL DEFAULT 24,
            active      INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    """
    )

    conn.commit()
    conn.close()


# =================================================
# Companies
# =================================================
def add_company(name: str, email: str, password: str) -> int:
    """Voegt een nieuw bedrijf toe en geeft ID terug."""
    conn = get_connection()
    try:
        c = conn.cursor()
        created_at = datetime.utcnow().isoformat()

        base = _slugify(name)
        slug = base
        i = 1
        while True:
            c.execute("SELECT 1 FROM companies WHERE slug = ?", (slug,))
            if not c.fetchone():
                break
            i += 1
            slug = f"{base}-{i}"

        c.execute(
            "INSERT INTO companies (name, email, password, paid, created_at, slug) "
            "VALUES (?,?,?,?,?,?)",
            (name, email, password, 0, created_at, slug),
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
    c.execute(
        "SELECT * FROM companies WHERE lower(email)=lower(?)", (email,)
    )
    row = c.fetchone()
    conn.close()
    return row


def is_company_paid(company_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT paid FROM companies WHERE id=?", (company_id,)
    )
    row = c.fetchone()
    conn.close()
    return bool(row and row[0])


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


def get_company_name_by_id(company_id: int) -> str | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT name FROM companies WHERE id=?", (company_id,)
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_company(company_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM companies WHERE id=?", (company_id,)
    )
    row = c.fetchone()
    conn.close()
    return row


def get_company_by_slug(slug: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM companies WHERE slug=?", (slug,)
    )
    row = c.fetchone()
    conn.close()
    return row


def get_company_slug(company_id: int) -> str | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT slug FROM companies WHERE id=?", (company_id,)
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


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


def get_company_logo(company_id: int) -> str | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT logo_path FROM companies WHERE id=?", (company_id,)
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def update_company_profile(
    company_id: int,
    name: str,
    email: str,
    password: str | None = None,
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

# (rest van je categories / services / slots / reminders functies zoals in je originele bestand)
