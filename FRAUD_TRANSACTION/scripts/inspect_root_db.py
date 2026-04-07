import sqlite3
p='database.db'
conn=sqlite3.connect(p)
cur=conn.cursor()
print('Tables:')
for row in cur.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"):
    print(row)

print('\nPRAGMA table_info(users):')
for row in cur.execute('PRAGMA table_info(users)'):
    print(row)
conn.close()
