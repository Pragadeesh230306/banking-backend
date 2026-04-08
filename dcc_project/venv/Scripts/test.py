import sqlite3

DB = "banking.db"

conn = sqlite3.connect(DB)
cursor = conn.cursor()

cursor.execute("""
INSERT INTO users(name, email, phone, password, income, tier, role, status)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "Admin",
    "@gmail.com",
    "9999999999",
    "admin123",
    1000000,
    "GOLD",
    "EMPLOYEE",
    "ACTIVE"
))

conn.commit()
conn.close()

print("✅ Employee added successfully")