import sqlite3
conn = sqlite3.connect("db/bot_database.db")
cursor = conn.cursor()
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
print("جدول feedbacks اضافه شد.")