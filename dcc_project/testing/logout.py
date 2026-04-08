from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = "banking.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    acc = data["account_number"]
    password = data["password"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM users
        WHERE account_number=? AND password=?
    """, (acc, password))

    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    # create session
    cursor.execute("""
        INSERT INTO sessions (account_number, login_time, status)
        VALUES (?, ?, 'ACTIVE')
    """, (acc, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Login successful"
    })


from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = "banking.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    acc = data["account_number"]
    password = data["password"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM users
        WHERE account_number=? AND password=?
    """, (acc, password))

    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    # create session
    cursor.execute("""
        INSERT INTO sessions (account_number, login_time, status)
        VALUES (?, ?, 'ACTIVE')
    """, (acc, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Login successful"
    })

