from flask import Flask, request, jsonify
import sqlite3
import jwt
import datetime
import random
from datetime import timedelta
from flask_mail import Mail, Message

app = Flask(__name__)

DB = "banking.db"
SECRET_KEY = "mysecretkey123"

# ================= EMAIL CONFIG =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_app_password'

mail = Mail(app)

# ================= DB =================
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# ================= GLOBAL =================
otp_store = {}
pending_users = {}

# ================= TIER =================
def get_tier(income):
    if income < 300000:
        return "SILVER"
    elif income < 700000:
        return "GOLD"
    elif income < 1500000:
        return "PLATINUM"
    else:
        return "DIAMOND"

# ================= JWT =================
def generate_token(user_id, email):
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.datetime.utcnow() + timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(token):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM token_blacklist WHERE token=?", (token,))
        if cursor.fetchone():
            return None

        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return None

def get_current_user():
    auth = request.headers.get("Authorization")
    if not auth:
        return None

    try:
        token = auth.split(" ")[1]
    except:
        return None

    return verify_token(token)

# ================= REGISTER =================
@app.route("/register", methods=["POST"])
def register():
    data = request.json

    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")
    income = float(data.get("income"))
    role = data.get("role", "CUSTOMER").upper()

    if role not in ["CUSTOMER", "EMPLOYEE"]:
        return jsonify({"error": "Invalid role"}), 400

    otp = str(random.randint(100000, 999999))

    otp_store[email] = {
        "otp": otp,
        "expiry": datetime.datetime.utcnow() + timedelta(minutes=5)
    }

    pending_users[email] = {
        "name": name,
        "phone": phone,
        "password": password,
        "income": income,
        "role": role
    }

    msg = Message(
        subject="OTP Verification",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )
    msg.body = f"Your OTP is {otp}"
    mail.send(msg)

    return jsonify({"message": "OTP sent"})

# ================= VERIFY REGISTER =================
@app.route("/verify-register", methods=["POST"])
def verify_register():
    data = request.json
    email = data.get("email")
    otp = data.get("otp")

    record = otp_store.get(email)

    if not record:
        return jsonify({"error": "OTP not found"}), 400

    if datetime.datetime.utcnow() > record["expiry"]:
        return jsonify({"error": "OTP expired"}), 400

    if record["otp"] != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    user = pending_users[email]
    tier = get_tier(user["income"])

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO users (name, email, phone, password, income, tier, role, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'INACTIVE')
    """, (
        user["name"], email, user["phone"],
        user["password"], user["income"],
        tier, user["role"]
    ))

    conn.commit()
    conn.close()

    del otp_store[email]
    del pending_users[email]

    return jsonify({"message": "Registered successfully", "tier": tier})

# ================= LOGIN =================
@app.route("/login", methods=["POST"])
def login():
    data = request.json

    email = data.get("email")
    password = data.get("password")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, email FROM users
        WHERE email=? AND password=?
    """, (email, password))

    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    token = generate_token(user["user_id"], user["email"])

    return jsonify({"token": token})

# ================= ACCOUNT =================
@app.route("/account", methods=["GET"])
def account():
    user = get_current_user()

    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cursor = conn.cursor()

    # 🔍 Get account using logged-in user_id
    cursor.execute("""
        SELECT account_number, account_type, account_tier, balance, status
        FROM accounts
        WHERE user_id = ?
    """, (user["user_id"],))

    account = cursor.fetchone()
    conn.close()

    if not account:
        return jsonify({"error": "Account not found"}), 404

    return jsonify(dict(account))
# ================= APPROVE =================
@app.route("/approve/<int:user_id>", methods=["POST"])
def approve(user_id):
    user = get_current_user()

    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT role FROM users WHERE id=?", (user["user_id"],))
    approver = cursor.fetchone()

    if approver["role"] != "EMPLOYEE":
        return jsonify({"error": "Only employee allowed"}), 403

    cursor.execute("UPDATE users SET status='ACTIVE' WHERE id=?", (user_id,))

    conn.commit()
    conn.close()

    return jsonify({"message": "Approved"})

# ================= LOGOUT =================
@app.route("/logout", methods=["POST"])
def logout():
    auth = request.headers.get("Authorization")

    if not auth:
        return jsonify({"error": "Token missing"}), 401

    token = auth.split(" ")[1]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO token_blacklist (token, created_at) VALUES (?, ?)",
        (token, str(datetime.datetime.utcnow()))
    )

    conn.commit()
    conn.close()

    return jsonify({"message": "Logged out"})
    
# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)