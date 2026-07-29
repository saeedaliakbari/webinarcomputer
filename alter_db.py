import sqlite3
conn = sqlite3.connect('db/bot_database.db')
conn.execute('ALTER TABLE ad_sessions ADD COLUMN video_link TEXT')
conn.commit()
conn.close()
print('ستون اضافه شد')