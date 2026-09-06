import sqlite3
conn = sqlite3.connect('db/bot_database.db')
conn.execute('SELECT id, title, description FROM ads')
conn.commit()
conn.close()
print('ستون اضافه شد')