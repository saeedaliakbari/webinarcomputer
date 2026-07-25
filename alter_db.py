import sqlite3
conn = sqlite3.connect("db/bot_database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submitted_by INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    photo_file_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_event_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pending_event_id INTEGER NOT NULL,
    session_time TEXT NOT NULL,
    FOREIGN KEY(pending_event_id) REFERENCES pending_events(id)
)
""")

conn.commit()
conn.close()
print("جدول‌ها اضافه شدند.")