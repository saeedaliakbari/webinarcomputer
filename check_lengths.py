import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "bot_database.db")

def calculate_message_length(title, description, session_count):
    header = f"📢 {title}\n\n"
    footer_sample = "\n\n🕒 جلسات:\n" + "\n".join(["1️⃣ 1405/05/05 - 18:00"] * session_count)
    return len(header) + len(description) + len(footer_sample)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT id, title, description FROM ads")
ads = cursor.fetchall()

for ad_id, title, description in ads:
    cursor.execute("SELECT COUNT(*) FROM ad_sessions WHERE ad_id = ?", (ad_id,))
    session_count = cursor.fetchone()[0]
    length = calculate_message_length(title, description, session_count)
    desc_len = len(description)
    print(f"آگهی #{ad_id} «{title}»: طول توضیحات={desc_len} | طول کل تخمینی={length} | تعداد جلسات={session_count}")

conn.close()