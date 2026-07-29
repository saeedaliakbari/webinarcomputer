import sqlite3
conn = sqlite3.connect('db/bot_database.db')
conn.execute('ALTER TABLE ad_sessions ADD COLUMN video_file_id TEXT')
conn.commit()
conn.close()
print('add video column')