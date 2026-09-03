import sqlite3
conn = sqlite3.connect('db/bot_database.db')
conn.execute('ALTER TABLE users ADD COLUMN quota INTEGER DEFAULT 10')
conn.commit()
conn.close()
print('ستون quota اضافه شد')

import sqlite3
conn = sqlite3.connect('db/bot_database.db')
conn.execute('ALTER TABLE reminders ADD COLUMN attempt_count INTEGER DEFAULT 0')
conn.commit()
conn.close()
print('ستون attempt_count اضافه شد')