from flask import Flask, request, jsonify
import sqlite3
import jwt
import datetime
import random
import time
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


# ================= OTP STORAGE =================
otp_store = {}
pending_users = {}
transfer_otp_store = {}
pending_transfer = {}


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
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return None


def get_current_user():
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    try:
        token = auth.split(" ")[1]
        return verify_token(token)
    except:
        return None


# ================= TIER =================
def get_tier(income):
    if income < 300000:
        return "SILVER"
    elif income < 700000:
        return "GOLD"
    elif income < 1500000:
        return "PLATINUM"
    return "DIAMOND"


# =========================================================
# 🧾 REGISTER + OTP
# =========================================================
@app.route("/register", methods=["POST"])
def register():
    data = request.json

    email = data["email"]
    otp = str(random.randint(100000, 999999))

    otp_store[email] = {
        "otp": otp,
        "expiry": datetime.datetime.utcnow() + timedelta(minutes=5)
    }

    pending_users[email] = data

    msg = Message(
        subject="OTP Verification",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )
    msg.body = f"Your OTP is {otp}"
    mail.send(msg)

    return jsonify({"message": "OTP sent"})


# =========================================================
# VERIFY REGISTER
# =========================================================
@app.route("/verify-register", methods=["POST"])
def verify_register():
    data = request.json
    email = data["email"]
    otp = data["otp"]

    if email not in otp_store:
        return jsonify({"error": "OTP not found"}), 400

    record = otp_store[email]

    if datetime.datetime.utcnow() > record["expiry"]:
        return jsonify({"error": "OTP expired"}), 400

    if record["otp"] != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    user = pending_users[email]
    tier = get_tier(float(user["income"]))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users(name, email, phone, password, income, tier, role, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
    """, (
        user["name"], email, user["phone"],
        user["password"], user["income"],
        tier, user.get("role", "CUSTOMER")
    ))

    conn.commit()
    conn.close()

    del otp_store[email]
    del pending_users[email]

    return jsonify({"message": "Registered", "tier": tier})


# =========================================================
# LOGIN
# =========================================================
@app.route("/login", methods=["POST"])
def login():
    data = request.json

    email = data["email"]
    password = data["password"]

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


# =========================================================
# BENEFICIARY (NAME BASED)
# =========================================================
@app.route("/add-beneficiary", methods=["POST"])
def add_beneficiary():
    user = get_current_user()
    data = request.json

    name = data["beneficiary_name"]
    acc_no = data["account_number"]
    ifsc = data["ifsc_code"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM beneficiaries
        WHERE user_id=? AND beneficiary_name=?
    """, (user["user_id"], name))

    if cursor.fetchone():
        return jsonify({"message": "Already exists"}), 200

    cursor.execute("""
        INSERT INTO beneficiaries(user_id, beneficiary_name, account_number, ifsc_code)
        VALUES (?, ?, ?, ?)
    """, (user["user_id"], name, acc_no, ifsc))

    conn.commit()
    conn.close()

    return jsonify({"message": "Beneficiary added"})


# =========================================================
# TRANSFER INITIATE (IMPS / NEFT / RTGS)
# =========================================================
@app.route("/transfer/initiate", methods=["POST"])
def initiate_transfer():
    user = get_current_user()
    data = request.json

    beneficiary_name = data["beneficiary_name"]
    amount = float(data["amount"])
    mode = data.get("mode", "NEFT").upper()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT account_number FROM accounts
        WHERE user_id=?
    """, (user["user_id"],))

    sender = cursor.fetchone()

    if not sender:
        return jsonify({"error": "Account not found"}), 404

    from_acc = sender["account_number"]

    cursor.execute("""
        SELECT account_number FROM beneficiaries
        WHERE user_id=? AND beneficiary_name=?
    """, (user["user_id"], beneficiary_name))

    ben = cursor.fetchone()

    if not ben:
        return jsonify({"error": "Beneficiary not found"}), 404

    to_acc = ben["account_number"]

    if mode == "RTGS" and amount <= 200000:
        return jsonify({"error": "RTGS only above 2 lakh"}), 400

    if mode not in ["IMPS", "NEFT", "RTGS"]:
        return jsonify({"error": "Invalid mode"}), 400

    charge = 15 if mode == "IMPS" else 0
    total = amount + charge

    otp = str(random.randint(100000, 999999))

    transfer_otp_store[user["email"]] = {
        "otp": otp,
        "expiry": datetime.datetime.utcnow() + timedelta(minutes=5)
    }

    pending_transfer[user["email"]] = {
        "from": from_acc,
        "to": to_acc,
        "amount": amount,
        "mode": mode,
        "charge": charge,
        "total": total
    }

    msg = Message(
        subject="Transfer OTP",
        sender=app.config['MAIL_USERNAME'],
        recipients=[user["email"]]
    )
    msg.body = f"OTP: {otp}"
    mail.send(msg)

    return jsonify({"message": "OTP sent"})


# =========================================================
# VERIFY TRANSFER
# =========================================================
@app.route("/transfer/verify", methods=["POST"])
def verify_transfer():
    user = get_current_user()
    email = user["email"]
    otp = request.json["otp"]

    if email not in transfer_otp_store:
        return jsonify({"error": "OTP missing"}), 400

    record = transfer_otp_store[email]

    if datetime.datetime.utcnow() > record["expiry"]:
        return jsonify({"error": "OTP expired"}), 400

    if record["otp"] != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    t = pending_transfer[email]

    conn = get_db()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN")

        cursor.execute("""
            SELECT balance FROM accounts WHERE account_number=?
        """, (t["from"],))
        sender = cursor.fetchone()

        cursor.execute("""
            SELECT balance FROM accounts WHERE account_number=?
        """, (t["to"],))
        receiver = cursor.fetchone()

        if sender["balance"] < t["total"]:
            raise Exception("Insufficient balance")

        cursor.execute("""
            UPDATE accounts SET balance = balance - ?
            WHERE account_number=?
        """, (t["total"], t["from"]))

        time.sleep(10 if t["mode"] in ["NEFT", "RTGS"] else 0)

        cursor.execute("""
            UPDATE accounts SET balance = balance + ?
            WHERE account_number=?
        """, (t["amount"], t["to"]))

        cursor.execute("""
            INSERT INTO transactions(from_account, to_account, amount, mode, charge, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'SUCCESS', ?)
        """, (
            t["from"], t["to"], t["amount"],
            t["mode"], t["charge"],
            str(datetime.datetime.utcnow())
        ))

        conn.commit()

        del transfer_otp_store[email]
        del pending_transfer[email]

        return jsonify({"message": "Transfer successful"})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400

    finally:
        conn.close()


# =========================================================
# MINI STATEMENT
# =========================================================
@app.route("/mini-statement/<acc>")
def mini_statement(acc):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM transactions
        WHERE from_account=? OR to_account=?
        ORDER BY created_at DESC
        LIMIT 10
    """, (acc, acc))

    rows = cursor.fetchall()

    return jsonify([
        {
            "from": r["from_account"],
            "to": r["to_account"],
            "amount": r["amount"],
            "mode": r["mode"],
            "status": r["status"]
        }
        for r in rows
    ])


# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    app.run(debug=True)