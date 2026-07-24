import sqlite3
conn = sqlite3.connect("bot_database.db")
conn.execute("ALTER TABLE ads ADD COLUMN photo_file_id TEXT")
conn.commit()
conn.close()
print("ستون اضافه شد")