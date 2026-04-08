from flask import Flask, request, jsonify
import sqlite3
import jwt
import datetime

app = Flask(__name__)

SECRET_KEY = "mysecretkey123"


def generate_token(user_id, account_no):
    payload = {
        "user_id": user_id,
        "account_no": account_no,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return None


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    account_no = data["account_no"]
    password = data["password"]

    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, account_no FROM users WHERE account_no=? AND password=?",
        (account_no, password)
    )
    user = cursor.fetchone()
    conn.close()

    if user:
        token = generate_token(user[0], user[1])
        return jsonify({"message": "Login success", "token": token})

    return jsonify({"error": "Invalid credentials"}), 401


@app.route("/account", methods=["GET"])
def account():
    token = request.headers.get("Authorization")

    if not token:
        return jsonify({"error": "Token missing"}), 401

    data = verify_token(token)

    if not data:
        return jsonify({"error": "Invalid token"}), 401

    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)


from flask import Flask, request, jsonify
import sqlite3
import jwt
import datetime

app = Flask(__name__)

SECRET_KEY = "mysecretkey123"


def generate_token(user_id, account_no):
    payload = {
        "user_id": user_id,
        "account_no": account_no,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return None


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    account_no = data["account_no"]
    password = data["password"]

    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, account_no FROM users WHERE account_no=? AND password=?",
        (account_no, password)
    )
    user = cursor.fetchone()
    conn.close()

    if user:
        token = generate_token(user[0], user[1])
        return jsonify({"message": "Login success", "token": token})

    return jsonify({"error": "Invalid credentials"}), 401


@app.route("/account", methods=["GET"])
def account():
    token = request.headers.get("Authorization")

    if not token:
        return jsonify({"error": "Token missing"}), 401

    data = verify_token(token)

    if not data:
        return jsonify({"error": "Invalid token"}), 401

    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)


from datetime import datetime
import sqlite3
from flask import request, jsonify

@app.route("/logout", methods=["POST"])
def logout():
    token = request.headers.get("Authorization")

    if not token:
        return jsonify({"error": "Token missing"}), 401

    conn = sqlite3.connect("bank.db")
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO token_blacklist (token, created_at) VALUES (?, ?)",
            (token, str(datetime.utcnow()))
        )
        conn.commit()
    except:
        pass  # token already blacklisted

    conn.close()

    return jsonify({"message": "Logged out successfully"})



