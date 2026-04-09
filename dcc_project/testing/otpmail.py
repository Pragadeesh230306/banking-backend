import sqlite3
from datetime import datetime

conn = sqlite3.connect("banking.db")
cursor = conn.cursor()

# ADD COLUMN (safe even if table already exists)
try:
    cursor.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
except:
    pass

# BACKFILL OLD USERS (important)
cursor.execute("""
    UPDATE users
    SET created_at = COALESCE(created_at, ?)
""", (datetime.utcnow().isoformat(),))

conn.commit()
conn.close()

print("Migration done")