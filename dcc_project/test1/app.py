from flask import Flask, request, jsonify
import sqlite3
import datetime
import random
import time
from datetime import timedelta
from flask_mail import Mail, Message
from flask_cors import CORS
import threading

app = Flask(__name__)
CORS(app, origins="*")

# ================= CONFIG =================
DB = "banking.db"
SECRET_KEY = "mysecretkey123"

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'pragdeezzh230306@gmail.com'
app.config['MAIL_PASSWORD'] = 'nzuu zcih rcsi omqh'

mail = Mail(app)

# ================= DB =================
def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ================= STORAGE =================
otp_store = {}
pending_users = {}
transfer_otp_store = {}
pending_transfer = {}

# ================= DB INIT =================
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        password TEXT,
        income REAL,
        tier TEXT,
        role TEXT,
        status TEXT,
        reset_otp TEXT,
        otp_expiry TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        account_number TEXT,
        account_type TEXT,
        account_tier TEXT,
        balance REAL,
        status TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_account TEXT,
        to_account TEXT,
        amount REAL,
        mode TEXT,
        charge REAL,
        status TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_number TEXT,
        loan_amount REAL,
        interest_rate REAL,
        tenure_months INTEGER,
        emi REAL,
        status TEXT,
        remaining_amount REAL,
        paid_amount REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS token_blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= HELPERS =================
def get_tier(income):
    if income < 300000:
        return "SILVER"
    elif income < 700000:
        return "GOLD"
    elif income < 1500000:
        return "PLATINUM"
    return "DIAMOND"

# ================= REGISTER =================
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

    try:
        msg = Message("OTP", sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f"OTP is {otp}"
        mail.send(msg)
    except:
        print("EMAIL FAILED")

    return jsonify({"message": "OTP sent"})


@app.route("/verify-register", methods=["POST"])
def verify_register():
    data = request.json
    email = data["email"]
    otp = data["otp"]

    if email not in otp_store:
        return jsonify({"error": "OTP not found"}), 400

    if otp_store[email]["otp"] != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    if datetime.datetime.utcnow() > otp_store[email]["expiry"]:
        return jsonify({"error": "Expired OTP"}), 400

    user = pending_users[email]
    tier = get_tier(float(user["income"]))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users(name,email,phone,password,income,tier,role,status)
        VALUES(?,?,?,?,?,?,?,'INACTIVE')
    """, (
        user["name"], email, user["phone"],
        user["password"], user["income"],
        tier, user.get("role", "CUSTOMER").upper()
    ))

    conn.commit()
    conn.close()

    return jsonify({"message": "Registered"})

# ================= LOGIN =================
@app.route("/login", methods=["POST"])
def login():
    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=?", (data["email"],))
    user = cursor.fetchone()

    conn.close()

    if not user or user["password"] != data["password"]:
        return jsonify({"error": "Invalid credentials"}), 401

    if user["status"] != "ACTIVE":
        return jsonify({"error": "Not approved"}), 403


    return jsonify({
        "user_id": user["user_id"],
        "role": user["role"],
        "email": user["email"]
    })

# ================= ACCOUNT =================
@app.route("/account", methods=["GET"])
def account():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
    acc = cursor.fetchone()

    if not acc:
        return jsonify({"error": "No account"}), 404

    cursor.execute("""
        SELECT 
        COALESCE(SUM(CASE WHEN to_account=? THEN amount ELSE 0 END),0)
        - COALESCE(SUM(CASE WHEN from_account=? THEN amount ELSE 0 END),0)
        AS balance
        FROM transactions
    """, (acc["account_number"], acc["account_number"]))

    bal = cursor.fetchone()["balance"]

    result = dict(acc)
    result["balance"] = float(bal)

    conn.close()
    return jsonify(result)

@app.route("/add-beneficiary", methods=["POST"])
def add_beneficiary():
    data = request.json

    user_id = data["user_id"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO beneficiaries(user_id, beneficiary_name, account_number, ifsc_code)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        data["beneficiary_name"],
        data["account_number"],
        data["ifsc_code"]
    ))

    conn.commit()
    conn.close()

    return jsonify({"message": "Beneficiary added"})
# =========================================================
@app.route("/transfer/initiate", methods=["POST"])
def initiate_transfer():
    data = request.json

    user_id = data["user_id"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT account_number FROM accounts WHERE user_id=?", (user_id,))
    sender = cursor.fetchone()

    cursor.execute("""
        SELECT account_number FROM beneficiaries
        WHERE user_id=? AND beneficiary_name=?
    """, (user_id, data["beneficiary_name"]))

    ben = cursor.fetchone()

    if not sender or not ben:
        return jsonify({"error": "Invalid accounts"}), 404

    amount = float(data["amount"])
    mode = data.get("mode", "NEFT").upper()

    charge = 15 if mode == "IMPS" else 0
    total = amount + charge

    otp = str(random.randint(100000, 999999))

    transfer_otp_store[user_id] = {
        "otp": otp,
        "expiry": datetime.datetime.utcnow() + timedelta(minutes=5)
    }

    pending_transfer[user_id] = {
        "from": sender["account_number"],
        "to": ben["account_number"],
        "amount": amount,
        "mode": mode,
        "charge": charge,
        "total": total
    }

    return jsonify({"message": "OTP sent"})
# =========================================================
# VERIFY TRANSFER
# =========================================================
@app.route("/transfer/verify", methods=["POST"])
def verify_transfer():
    data = request.json
    user_id = data["user_id"]
    otp = data["otp"]

    if user_id not in transfer_otp_store:
        return jsonify({"error": "OTP not found"}), 400

    if transfer_otp_store[user_id]["otp"] != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    t = pending_transfer[user_id]

    conn = get_db()
    cursor = conn.cursor()

    conn.execute("BEGIN")

    cursor.execute("SELECT balance FROM accounts WHERE account_number=?", (t["from"],))
    sender = cursor.fetchone()

    if sender["balance"] < t["total"]:
        return jsonify({"error": "Insufficient balance"}), 400

    cursor.execute("UPDATE accounts SET balance = balance - ? WHERE account_number=?",
                   (t["total"], t["from"]))

    if t["mode"] in ["NEFT", "RTGS"]:
        time.sleep(5)

    cursor.execute("UPDATE accounts SET balance = balance + ? WHERE account_number=?",
                   (t["amount"], t["to"]))

    cursor.execute("""
        INSERT INTO transactions(from_account, to_account, amount, mode, charge, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'SUCCESS', ?)
    """, (t["from"], t["to"], t["amount"], t["mode"], t["charge"], str(datetime.datetime.utcnow())))

    conn.commit()

    del transfer_otp_store[user_id]
    del pending_transfer[user_id]

    return jsonify({"message": "Transfer successful"})


# ================= LOANS =================
@app.route("/loan/request", methods=["POST"])
def loan_request():
    data = request.json
    user_id = data["user_id"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM accounts 
        WHERE account_number=? AND user_id=?
    """, (data["account_number"], user_id))

    acc = cursor.fetchone()

    if not acc:
        return jsonify({"error": "Invalid account"}), 403

    rate_map = {"SILVER": 12, "GOLD": 10, "PLATINUM": 8, "DIAMOND": 6}
    rate = rate_map.get(acc["account_tier"], 12)

    amount = float(data["loan_amount"])
    tenure = int(data["tenure_months"])

    interest = (amount * rate * tenure) / 1200
    total = amount + interest
    emi = total / tenure

    cursor.execute("""
        INSERT INTO loans(account_number,loan_amount,interest_rate,
        tenure_months,emi,status,remaining_amount,paid_amount)
        VALUES(?,?,?,?,?,'ACTIVE',?,0)
    """, (acc["account_number"], amount, rate, tenure, emi, total))

    conn.commit()
    conn.close()

    return jsonify({"emi": emi, "total": total})

@app.route("/loan/pay-emi", methods=["POST"])
def pay_emi():
    data = request.json
    user_id = data["user_id"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT l.*, a.user_id 
        FROM loans l
        JOIN accounts a ON l.account_number=a.account_number
        WHERE l.id=?
    """, (data["loan_id"],))

    loan = cursor.fetchone()

    if not loan or loan["user_id"] != int(user_id):
        return jsonify({"error": "Invalid loan"}), 403

    remaining = float(loan["remaining_amount"])
    pay = float(data["amount"])

    remaining = max(0, remaining - pay)
    status = "CLOSED" if remaining == 0 else "ACTIVE"

    cursor.execute("""
        UPDATE loans SET remaining_amount=?, status=? WHERE id=?
    """, (remaining, status, data["loan_id"]))

    conn.commit()
    conn.close()

    return jsonify({"remaining": remaining, "status": status})

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email required"}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "User not found"}), 404

    otp = str(random.randint(100000, 999999))

    otp_store[email] = {
        "otp": otp,
        "expiry": datetime.datetime.utcnow() + timedelta(minutes=5)
    }

    try:
        msg = Message(
            "Password Reset OTP",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        msg.body = f"Your OTP for password reset is: {otp}"
        mail.send(msg)
    except Exception as e:
        print("EMAIL ERROR:", e)

    return jsonify({"message": "OTP sent to email"})

#@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()

    email = data.get("email")
    otp_input = data.get("otp")
    new_password = data.get("new_password")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 404

    # check OTP from RAM store (NOT DB)
    if email not in otp_store:
        return jsonify({"error": "OTP not found"}), 400

    record = otp_store[email]

    if datetime.datetime.utcnow() > record["expiry"]:
        return jsonify({"error": "OTP expired"}), 400

    if record["otp"] != otp_input:
        return jsonify({"error": "Invalid OTP"}), 400

    cursor.execute("""
        UPDATE users SET password=? WHERE email=?
    """, (new_password, email))

    conn.commit()
    conn.close()

    del otp_store[email]

    return jsonify({"message": "Password reset successful"})


@app.route("/verify-reset-otp", methods=["POST"])
def verify_reset_otp():
    data = request.get_json()
    email = data.get("email")
    otp = data.get("otp")

    if email not in otp_store:
        return jsonify({"error": "OTP not found"}), 400

    record = otp_store[email]

    if datetime.datetime.utcnow() > record["expiry"]:
        return jsonify({"error": "OTP expired"}), 400

    if record["otp"] != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    return jsonify({"message": "OTP verified"})


# ================= LOGOUT =================
@app.route("/logout", methods=["POST"])
def logout():
    return jsonify({
        "message": "Logged out successfully"
    })

@app.route("/mini-statement/<acc>", methods=["GET"])
def mini_statement(acc):
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        # ensure account belongs to user
        cursor.execute("""
            SELECT account_number 
            FROM accounts 
            WHERE account_number=? AND user_id=?
        """, (acc, user_id))

        if not cursor.fetchone():
            return jsonify({"error": "Invalid account"}), 403

        # fetch last 10 transactions
        cursor.execute("""
            SELECT *
            FROM transactions
            WHERE from_account=? OR to_account=?
            ORDER BY created_at DESC
            LIMIT 10
        """, (acc, acc))

        rows = cursor.fetchall()
        result = [dict(r) for r in rows] if rows else []

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)