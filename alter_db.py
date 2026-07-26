import sqlite3
conn = sqlite3.connect("db/bot_database.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    first_seen TEXT DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
conn.close()
print("جدول users اضافه شد.")