from flask import Flask, request, jsonify
import sqlite3
import random
from datetime import datetime, timedelta
from flask_mail import Mail, Message

app = Flask(__name__)
DB = "banking.db"

# ================= EMAIL CONFIG =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'pragdeezzh230306@gmail.com'
app.config['MAIL_PASSWORD'] = 'nzuu zcih rcsi omqh'

mail = Mail(app)

# ================= DB CONNECTION =================
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# ================= GLOBAL STORAGE =================
otp_store = {}
pending_users = {}

# ================= TIER LOGIC =================
def get_tier(income):
    if income < 300000:
        return "SILVER"
    elif income < 700000:
        return "GOLD"
    elif income < 1500000:
        return "PLATINUM"
    else:
        return "DIAMOND"

# =================================================
# 📝 REGISTER (SEND OTP)
# =================================================
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()

        name = data.get("name")
        email = data.get("email")
        phone = data.get("phone")
        password = data.get("password")
        income = float(data.get("income"))
        role = data.get("role", "CUSTOMER").upper()

        if role not in ["CUSTOMER", "EMPLOYEE"]:
            return jsonify({"error": "Invalid role"}), 400

        if not all([name, email, phone, password, income]):
            return jsonify({"error": "All fields required"}), 400

        # OTP
        otp = str(random.randint(100000, 999999))

        otp_store[email] = {
            "otp": otp,
            "expiry": datetime.utcnow() + timedelta(minutes=5)
        }

        pending_users[email] = {
            "name": name,
            "phone": phone,
            "password": password,
            "income": income,
            "role": role
        }

        # Send Email
        msg = Message(
            subject="Bank Registration OTP",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        msg.body = f"Your OTP is {otp}. Valid for 5 minutes."
        mail.send(msg)

        return jsonify({"message": "OTP sent to email"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =================================================
# 🔐 VERIFY REGISTER
# =================================================
@app.route('/verify-register', methods=['POST'])
def verify_register():
    try:
        data = request.get_json()
        email = data.get("email")
        otp = data.get("otp")

        if email not in otp_store:
            return jsonify({"error": "OTP not found"}), 400

        record = otp_store[email]

        if datetime.utcnow() > record["expiry"]:
            return jsonify({"error": "OTP expired"}), 400

        if record["otp"] != otp:
            return jsonify({"error": "Invalid OTP"}), 400

        user = pending_users[email]
        tier = get_tier(user["income"])

        conn = get_db()
        cursor = conn.cursor()

        # Insert user
        cursor.execute("""
        INSERT INTO users (name, email, phone, password, income, tier, role, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            user["name"],
            email,
            user["phone"],
            user["password"],
            user["income"],
            tier,
            user["role"],
            "INACTIVE"
        ))

        user_id = cursor.lastrowid

        # KYC
        cursor.execute("""
        INSERT INTO kyc_verification (user_id, status)
        VALUES (?, ?)
        """, (user_id, "PENDING"))

        # Documents
        cursor.execute("""
        INSERT INTO documents (user_id, pan_card_path, income_certificate_path, verification_status, uploaded_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, "", "", "PENDING"))

        # Notification
        cursor.execute("""
        INSERT INTO notifications (user_id, message, type, status, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            user_id,
            "Registration submitted. Waiting for approval",
            "INFO",
            "UNREAD"
        ))

        conn.commit()
        conn.close()

        del otp_store[email]
        del pending_users[email]

        return jsonify({
            "message": "Registration successful",
            "user_id": user_id,
            "tier": tier
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =================================================
# 🏦 APPROVE USER (EMPLOYEE ONLY)
# =================================================
@app.route('/approve/<int:user_id>', methods=['POST'])
def approve(user_id):
    try:
        data = request.get_json()
        approver_id = data.get("approver_id")

        conn = get_db()
        cursor = conn.cursor()

        # Check employee
        cursor.execute("SELECT role FROM users WHERE user_id=?", (approver_id,))
        approver = cursor.fetchone()

        if not approver or approver["role"] != "EMPLOYEE":
            return jsonify({"error": "Only employees can approve"}), 403

        # Check target user
        cursor.execute("SELECT role FROM users WHERE user_id=?", (user_id,))
        target = cursor.fetchone()

        if not target:
            return jsonify({"error": "User not found"}), 404

        if target["role"] != "CUSTOMER":
            return jsonify({"error": "Only customers can have accounts"}), 400

        # Approve KYC
        cursor.execute("UPDATE kyc_verification SET status='APPROVED' WHERE user_id=?", (user_id,))
        cursor.execute("UPDATE users SET status='ACTIVE' WHERE user_id=?", (user_id,))

        # Create account
        account_number = str(random.randint(1000000000, 9999999999))

        cursor.execute("""
        INSERT INTO accounts (user_id, account_number, account_type, account_tier, balance, interest_rate, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            user_id,
            account_number,
            "SAVINGS",
            "GOLD",
            0,
            4.0,
            "ACTIVE"
        ))

        conn.commit()
        conn.close()

        return jsonify({
            "message": "Approved successfully",
            "account_number": account_number
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =================================================
# 📄 GET ACCOUNT
# =================================================
@app.route('/account/<int:user_id>', methods=['GET'])
def get_account(user_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT account_number, account_type, account_tier, balance, status
    FROM accounts WHERE user_id=?
    """, (user_id,))

    acc = cursor.fetchone()
    conn.close()

    if not acc:
        return jsonify({"error": "Account not found"}), 404

    return jsonify(dict(acc))

# =================================================
# 🚀 RUN
# =================================================
if __name__ == '__main__':
    app.run(debug=True)