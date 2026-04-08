from flask import Flask, request, jsonify
import sqlite3
import jwt
import datetime
import random
import time
from datetime import timedelta
from flask_mail import Mail, Message
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="*")

DB = "banking.db"
SECRET_KEY = "mysecretkey123"

# ================= EMAIL CONFIG =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'pragdeezzh230306@gmail.com'
app.config['MAIL_PASSWORD'] = 'nzuu zcih rcsi omqh'

mail = Mail(app)

# ================= DB =================
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# ================= STORAGE =================
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

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM token_blacklist WHERE token=?", (token,))
        if cursor.fetchone():
            conn.close()
            return None
        conn.close()

        return verify_token(token)

    except:
        return None
    
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # USERS TABLE
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
        otp_expiry TEXT
    )
    """)
    cursor.execute("""
CREATE TABLE IF NOT EXISTS beneficiaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    beneficiary_name TEXT,
    account_number TEXT,
    ifsc_code TEXT
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

    # ACCOUNTS TABLE
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

    # TOKEN BLACKLIST
    cursor.execute("""
CREATE TABLE IF NOT EXISTS token_blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT,
    created_at TEXT
)
""")

    conn.commit()
    conn.close()

    
def create_admin_if_not_exists():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email='admin@gmail.com'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users(name,email,phone,password,income,tier,role,status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Admin",
            "admin@gmail.com",
            "9999999999",
            "admin123",
            1000000,
            "GOLD",
            "EMPLOYEE",
            "ACTIVE"
        ))
        conn.commit()

    conn.close()
def create_admin_if_not_exists():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email='admin@gmail.com'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users(name,email,phone,password,income,tier,role,status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Admin",
            "admin@gmail.com",
            "9999999999",
            "admin123",
            1000000,
            "GOLD",
            "EMPLOYEE",
            "ACTIVE"
        ))
        conn.commit()

    conn.close()
init_db()
create_admin_if_not_exists()  # 🔥 CALL THIS

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

# =========================================================
# REGISTER + OTP
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

    msg = Message("OTP Verification",
                  sender=app.config['MAIL_USERNAME'],
                  recipients=[email])
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
        VALUES (?, ?, ?, ?, ?, ?, ?, 'INACTIVE')
    """, (
        user["name"], email, user["phone"],
        user["password"], user["income"],
        tier, user.get("role", "CUSTOMER").upper()
    ))

    conn.commit()
    conn.close()

    del otp_store[email]
    del pending_users[email]

    return jsonify({"message": "Registered. Wait for approval", "tier": tier})

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
        SELECT user_id, email, password, status FROM users
        WHERE email=?
    """, (email,))

    user = cursor.fetchone()
    conn.close()

    if not user or user["password"] != password:
        return jsonify({"error": "Invalid credentials"}), 401

    if user["status"] != "ACTIVE":
        return jsonify({"error": "Account not approved"}), 403

    token = generate_token(user["user_id"], user["email"])
    return jsonify({"token": token})

# =========================================================
# ACCOUNT
# =========================================================
@app.route("/account", methods=["GET"])
def account():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT account_number, account_type, account_tier, balance, status
        FROM accounts WHERE user_id=?
    """, (user["user_id"],))

    acc = cursor.fetchone()
    conn.close()

    if not acc:
        return jsonify({"error": "Account not found"}), 404

    return jsonify(dict(acc))

# =========================================================
# APPROVE USER
# =========================================================
@app.route("/approve/<int:user_id>", methods=["POST"])
def approve(user_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT role FROM users WHERE user_id=?", (user["user_id"],))
    approver = cursor.fetchone()

    if not approver or approver["role"] != "EMPLOYEE":
        return jsonify({"error": "Only employee allowed"}), 403

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    target = cursor.fetchone()

    if not target:
        return jsonify({"error": "User not found"}), 404

    cursor.execute("UPDATE users SET status='ACTIVE' WHERE user_id=?", (user_id,))

    acc_no = str(random.randint(1000000000, 9999999999))

    cursor.execute("""
        INSERT INTO accounts(user_id, account_number, account_type, account_tier, balance, status)
        VALUES (?, ?, 'SAVINGS', ?, 0, 'ACTIVE')
    """, (user_id, acc_no, target["tier"]))

    conn.commit()
    conn.close()

    return jsonify({"message": "Approved", "account_number": acc_no})

# =========================================================
# LOGOUT
# =========================================================
@app.route("/logout", methods=["POST"])
def logout():
    auth = request.headers.get("Authorization")
    if not auth:
        return jsonify({"error": "Token missing"}), 401

    token = auth.split(" ")[1]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO token_blacklist(token, created_at) VALUES (?, ?)",
                   (token, str(datetime.datetime.utcnow())))

    conn.commit()
    conn.close()

    return jsonify({"message": "Logged out"})

# =========================================================
# ADD BENEFICIARY
# =========================================================
@app.route("/add-beneficiary", methods=["POST"])
def add_beneficiary():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO beneficiaries(user_id, beneficiary_name, account_number, ifsc_code)
        VALUES (?, ?, ?, ?)
    """, (
        user["user_id"],
        data["beneficiary_name"],
        data["account_number"],
        data["ifsc_code"]
    ))

    conn.commit()
    conn.close()

    return jsonify({"message": "Beneficiary added"})

# =========================================================
# TRANSFER INITIATE
# =========================================================
@app.route("/transfer/initiate", methods=["POST"])
def initiate_transfer():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT account_number FROM accounts WHERE user_id=?", (user["user_id"],))
    sender = cursor.fetchone()

    cursor.execute("""
        SELECT account_number FROM beneficiaries
        WHERE user_id=? AND beneficiary_name=?
    """, (user["user_id"], data["beneficiary_name"]))

    ben = cursor.fetchone()

    if not sender or not ben:
        return jsonify({"error": "Invalid accounts"}), 404

    amount = float(data["amount"])
    mode = data.get("mode", "NEFT").upper()

    charge = 15 if mode == "IMPS" else 0
    total = amount + charge

    otp = str(random.randint(100000, 999999))

    transfer_otp_store[user["email"]] = {
        "otp": otp,
        "expiry": datetime.datetime.utcnow() + timedelta(minutes=5)
    }

    pending_transfer[user["email"]] = {
        "from": sender["account_number"],
        "to": ben["account_number"],
        "amount": amount,
        "mode": mode,
        "charge": charge,
        "total": total
    }

    msg = Message("Transfer OTP", sender=app.config['MAIL_USERNAME'], recipients=[user["email"]])
    msg.body = f"OTP: {otp}"
    mail.send(msg)

    return jsonify({"message": "OTP sent"})

# =========================================================
# VERIFY TRANSFER
# =========================================================
@app.route("/transfer/verify", methods=["POST"])
def verify_transfer():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    email = user["email"]
    otp = request.json["otp"]

    if email not in transfer_otp_store or transfer_otp_store[email]["otp"] != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    t = pending_transfer[email]

    conn = get_db()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN")

        cursor.execute("SELECT balance FROM accounts WHERE account_number=?", (t["from"],))
        sender = cursor.fetchone()

        if sender["balance"] < t["total"]:
            raise Exception("Insufficient balance")

        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE account_number=?", (t["total"], t["from"]))

        if t["mode"] in ["NEFT", "RTGS"]:
            time.sleep(5)

        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE account_number=?", (t["amount"], t["to"]))

        cursor.execute("""
            INSERT INTO transactions(from_account, to_account, amount, mode, charge, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'SUCCESS', ?)
        """, (t["from"], t["to"], t["amount"], t["mode"], t["charge"], str(datetime.datetime.utcnow())))

        conn.commit()

        del transfer_otp_store[email]
        del pending_transfer[email]

        return jsonify({"message": "Transfer successful"})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)})

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
        ORDER BY created_at DESC LIMIT 10
    """, (acc, acc))

    rows = cursor.fetchall()
    return jsonify([dict(r) for r in rows])

# =========================================================
# LOAN REQUEST
# =========================================================
@app.route("/loan/request", methods=["POST"])
def loan_request():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    acc_no = data["account_number"]
    amount = float(data["loan_amount"])
    tenure = int(data["tenure_months"])

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM accounts WHERE account_number=? AND user_id=?", (acc_no, user["user_id"]))
    acc = cursor.fetchone()

    if not acc:
        return jsonify({"error": "Invalid account"}), 403

    tier = acc["account_tier"]

    rates = {"SILVER": 12, "GOLD": 10, "PLATINUM": 8, "DIAMOND": 6}
    rate = rates.get(tier, 12)

    interest = (amount * rate * tenure) / 1200
    total = amount + interest
    emi = total / tenure

    cursor.execute("""
        INSERT INTO loans(account_number, loan_amount, interest_rate, tenure_months, emi,
        status, remaining_amount, paid_amount)
        VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, 0)
    """, (acc_no, amount, rate, tenure, emi, total))

    conn.commit()
    conn.close()

    return jsonify({"message": "Loan approved", "emi": round(emi, 2)})

# =========================================================
# PAY EMI
# =========================================================
@app.route("/loan/pay-emi", methods=["POST"])
def pay_emi():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    loan_id = data["loan_id"]
    amount = float(data["amount"])

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT l.*, a.user_id FROM loans l
        JOIN accounts a ON l.account_number = a.account_number
        WHERE l.id=?
    """, (loan_id,))
    loan = cursor.fetchone()

    if not loan or loan["user_id"] != user["user_id"]:
        return jsonify({"error": "Invalid loan"}), 403

    new_remaining = loan["remaining_amount"] - amount
    status = "ACTIVE" if new_remaining > 0 else "CLOSED"

    cursor.execute("""
        UPDATE loans SET remaining_amount=?, status=? WHERE id=?
    """, (new_remaining, status, loan_id))

    conn.commit()
    conn.close()

    return jsonify({"message": "EMI paid", "remaining": new_remaining})

# =========================================================
# APPLY PENALTY
# =========================================================
@app.route("/loan/apply-penalty", methods=["POST"])
def apply_penalty():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT role FROM users WHERE user_id=?", (user["user_id"],))
    role = cursor.fetchone()

    if not role or role["role"] != "EMPLOYEE":
        return jsonify({"error": "Only employee allowed"}), 403

    cursor.execute("""
        SELECT l.*, a.account_tier FROM loans l
        JOIN accounts a ON l.account_number = a.account_number
        WHERE l.status!='CLOSED'
    """)
    loans = cursor.fetchall()

    for loan in loans:
        rates = {"SILVER": 0.02, "GOLD": 0.015, "PLATINUM": 0.01, "DIAMOND": 0.005}
        penalty = loan["remaining_amount"] * rates.get(loan["account_tier"], 0.02)

        cursor.execute("""
            UPDATE loans SET remaining_amount=remaining_amount+? WHERE id=?
        """, (penalty, loan["id"]))

    conn.commit()
    conn.close()

    return jsonify({"message": "Penalty applied"})


# =========================================================
# FORGOT PASSWORD (OTP)
# =========================================================
@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()

    acc_no = data["account_number"]
    phone = data["mobile"]
    email = data["email"]

    conn = get_db()
    cursor = conn.cursor()

    # 🔍 verify using JOIN (correct way)
    cursor.execute("""
        SELECT u.* FROM users u
        JOIN accounts a ON u.user_id = a.user_id
        WHERE a.account_number=? AND u.phone=? AND u.email=?
    """, (acc_no, phone, email))

    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "Invalid account details"}), 401

    otp = str(random.randint(100000, 999999))
    expiry = (datetime.datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE users SET reset_otp=?, otp_expiry=?
        WHERE user_id=?
    """, (otp, expiry, user["user_id"]))

    conn.commit()
    conn.close()

    print(f"[SMS] OTP: {otp}")
    print(f"[EMAIL] OTP: {otp}")

    return jsonify({"message": "OTP sent", "validity": "5 minutes"})

# =========================================================
# RESET PASSWORD
# =========================================================
@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()

    acc_no = data["account_number"]
    otp_input = data["otp"]
    new_password = data["new_password"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT u.* FROM users u
        JOIN accounts a ON u.user_id = a.user_id
        WHERE a.account_number=?
    """, (acc_no,))

    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "Account not found"}), 404

    if user["reset_otp"] != otp_input:
        return jsonify({"error": "Invalid OTP"}), 400

    if not user["otp_expiry"]:
        return jsonify({"error": "OTP not generated"}), 400

    expiry = datetime.datetime.strptime(user["otp_expiry"], "%Y-%m-%d %H:%M:%S")

    if datetime.datetime.now() > expiry:
        return jsonify({"error": "OTP expired"}), 400

    # 🔐 update password
    cursor.execute("""
        UPDATE users
        SET password=?, reset_otp=NULL, otp_expiry=NULL
        WHERE user_id=?
    """, (new_password, user["user_id"]))

    conn.commit()
    conn.close()

    return jsonify({"message": "Password reset successful"})

# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)