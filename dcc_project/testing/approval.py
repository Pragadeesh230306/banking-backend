from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

DB = "banking.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- LOGIN API ----------------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data["email"]
    password = data["password"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, email, tier, status, account_number
        FROM users
        WHERE email=? AND password=?
    """, (email, password))

    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    if user["status"] != "ACTIVE":
        return jsonify({"error": "Account not active yet"}), 403

    return jsonify({
        "message": "Login successful",
        "user_id": user["id"],
        "name": user["name"],
        "tier": user["tier"],
        "account_number": user["account_number"]
    })


if __name__ == "__main__":
    app.run(debug=True)