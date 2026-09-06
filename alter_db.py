import sqlite3
conn = sqlite3.connect('db/bot_database.db')
conn.execute('ALTER TABLE ads ADD COLUMN channel_photo_message_id TEXT')
conn.commit()
conn.close()
print('ستون اضافه شد')