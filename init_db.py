import sqlite3

conn = sqlite3.connect("db/bot_database.db")
cursor = conn.cursor()

# cursor.execute("DROP TABLE IF EXISTS reminders")
# cursor.execute("DROP TABLE IF EXISTS ad_sessions")
# cursor.execute("DROP TABLE IF EXISTS ads")

cursor.execute("""
CREATE TABLE ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    photo_file_id TEXT,
    channel_message_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE ad_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_id INTEGER NOT NULL,
    session_time TEXT NOT NULL,
    FOREIGN KEY(ad_id) REFERENCES ads(id)
)
""")

cursor.execute("""
CREATE TABLE reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    remind_at TEXT NOT NULL,
    sent INTEGER DEFAULT 0,
    UNIQUE(session_id, user_id),
    FOREIGN KEY(session_id) REFERENCES ad_sessions(id)
)
""")

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

cursor.execute("""
CREATE TABLE IF NOT EXISTS feedbacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    reply TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    replied INTEGER DEFAULT 0
)
""")
conn.commit()
conn.close()
print("دیتابیس بازسازی شد.")