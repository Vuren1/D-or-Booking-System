import sqlite3
import os

# Pad naar de database
DB_PATH = os.path.join("data", "bookings.db")

def get_connection():
    # Zorgt ervoor dat de map bestaat
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Tabel voor bedrijven (companies)
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

    # Tabel voor categorieën
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT,
            description TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # Tabel voor diensten
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

    # Tabel voor beschikbaarheid
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

    # Tabel voor boekingen
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

    # Tabel voor boekingsitems (met snapshot kolommen)
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

    # Tabel voor herinneringen-instellingen
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

# Voer init_db() uit bij het starten van de app
if __name__ == "__main__":
    init_db()
