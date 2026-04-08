from flask import Flask, request, jsonify
import sqlite3
import time
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
daily_limit = {}
pending_transfer = {}


# ================= OTP LIMIT =================
def check_limit(email):
    today = datetime.utcnow().date()

    if email not in daily_limit:
        daily_limit[email] = {"date": today, "count": 0}

    if daily_limit[email]["date"] != today:
        daily_limit[email] = {"date": today, "count": 0}

    if daily_limit[email]["count"] >= 5:
        return False

    daily_limit[email]["count"] += 1
    return True


# =================================================
# 📧 SEND OTP
# =================================================
@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    email = data["email"]

    if not check_limit(email):
        return jsonify({"error": "Daily OTP limit reached"}), 400

    otp = str(random.randint(100000, 999999))

    otp_store[email] = {
        "otp": otp,
        "expiry": datetime.utcnow() + timedelta(minutes=5)
    }

    msg = Message(
        subject="Bank OTP Verification",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )

    msg.body = f"Your OTP is {otp}. Valid for 5 minutes."
    mail.send(msg)

    return jsonify({"message": "OTP sent"})


# =================================================
# 🔐 VERIFY OTP (standalone)
# =================================================
@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    email = data["email"]
    otp = data["otp"]

    record = otp_store.get(email)

    if not record:
        return jsonify({"error": "OTP not found"}), 400

    if datetime.utcnow() > record["expiry"]:
        return jsonify({"error": "OTP expired"}), 400

    if record["otp"] != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    del otp_store[email]

    return jsonify({"message": "OTP verified"})


# =================================================
# 🧾 ADD BENEFICIARY
# =================================================
@app.route("/add-beneficiary", methods=["POST"])
def add_beneficiary():
    data = request.get_json()

    acc_no = data["account_number"]
    name = data["account_holder_name"]
    ifsc = data["ifsc_code"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM accounts
        WHERE account_number=? AND account_holder_name=? AND ifsc_code=?
    """, (acc_no, name, ifsc))

    if not cursor.fetchone():
        return jsonify({"error": "Invalid account details"}), 400

    cursor.execute("SELECT * FROM beneficiaries WHERE account_number=?", (acc_no,))
    if cursor.fetchone():
        return jsonify({"message": "Already exists"})

    cursor.execute("""
        INSERT INTO beneficiaries (account_number, account_holder_name, ifsc_code)
        VALUES (?, ?, ?)
    """, (acc_no, name, ifsc))

    conn.commit()
    conn.close()

    return jsonify({"message": "Beneficiary added"})


# =================================================
# 💸 INITIATE TRANSFER (OTP LINKED)
# =================================================
@app.route("/transfer/initiate", methods=["POST"])
def initiate_transfer():
    data = request.get_json()

    from_acc = data["from_account"]
    to_acc = data["to_account"]
    amount = float(data["amount"])
    email = data["email"]

    otp = str(random.randint(100000, 999999))

    otp_store[email] = {
        "otp": otp,
        "expiry": datetime.utcnow() + timedelta(minutes=5)
    }

    pending_transfer[email] = {
        "from": from_acc,
        "to": to_acc,
        "amount": amount
    }

    msg = Message(
        subject="Transfer OTP",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )

    msg.body = f"Your transfer OTP is {otp}. Valid for 5 minutes."
    mail.send(msg)

    return jsonify({"message": "OTP sent for transfer"})


# =================================================
# 💸 VERIFY OTP + EXECUTE TRANSFER
# =================================================
@app.route("/transfer/verify", methods=["POST"])
def verify_transfer():
    data = request.get_json()

    email = data["email"]
    otp = data["otp"]

    if email not in otp_store:
        return jsonify({"error": "OTP not found"}), 400

    record = otp_store[email]

    if datetime.utcnow() > record["expiry"]:
        return jsonify({"error": "OTP expired"}), 400

    if record["otp"] != otp:
        return jsonify({"error": "Invalid OTP"}), 400

    if email not in pending_transfer:
        return jsonify({"error": "No pending transfer"}), 400

    transfer = pending_transfer[email]

    from_acc = transfer["from"]
    to_acc = transfer["to"]
    amount = transfer["amount"]

    conn = get_db()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN TRANSACTION")

        cursor.execute("SELECT * FROM accounts WHERE account_number=?", (from_acc,))
        sender = cursor.fetchone()

        if not sender:
            raise Exception("Sender not found")

        cursor.execute("SELECT * FROM beneficiaries WHERE account_number=?", (to_acc,))
        if not cursor.fetchone():
            raise Exception("Beneficiary not registered")

        if sender["balance"] < amount:
            raise Exception("Insufficient balance")

        cursor.execute("""
            UPDATE accounts SET balance = balance - ?
            WHERE account_number=?
        """, (amount, from_acc))

        cursor.execute("""
            UPDATE accounts SET balance = balance + ?
            WHERE account_number=?
        """, (amount, to_acc))

        cursor.execute("""
            INSERT INTO transactions
            (from_account, to_account, amount, mode, charge, status, created_at)
            VALUES (?, ?, ?, 'OTP_TRANSFER', 0, 'SUCCESS', ?)
        """, (from_acc, to_acc, amount, str(datetime.utcnow())))

        conn.commit()

        del otp_store[email]
        del pending_transfer[email]

        return jsonify({"message": "Transfer successful"})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400

    finally:
        conn.close()


# =================================================
# 🏦 EMPLOYEE DEPOSIT
# =================================================
@app.route("/employee/deposit", methods=["POST"])
def employee_deposit():
    data = request.get_json()

    acc = data["account_number"]
    amount = float(data["amount"])

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM accounts WHERE account_number=?", (acc,))
    if not cursor.fetchone():
        return jsonify({"error": "Account not found"}), 404

    time.sleep(1)

    cursor.execute("""
        UPDATE accounts SET balance = balance + ?
        WHERE account_number=?
    """, (amount, acc))

    cursor.execute("""
        INSERT INTO transactions
        (from_account, to_account, amount, mode, charge, status, created_at)
        VALUES (?, ?, ?, 'CASH_DEPOSIT', 0, 'SUCCESS', ?)
    """, ("EMPLOYEE", acc, amount, str(datetime.utcnow())))

    conn.commit()
    conn.close()

    return jsonify({"message": "Deposit successful"})


# =================================================
# 📄 MINI STATEMENT
# =================================================
@app.route("/mini-statement/<acc>", methods=["GET"])
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
    conn.close()

    result = []

    for r in rows:
        txn_type = "DEBIT" if r["from_account"] == acc else "CREDIT"

        result.append({
            "type": txn_type,
            "from": r["from_account"],
            "to": r["to_account"],
            "amount": r["amount"],
            "mode": r["mode"],
            "charge": r["charge"],
            "status": r["status"],
            "date": r["created_at"]
        })

    return jsonify({"account": acc, "statement": result})


# =================================================
# 🚀 RUN APP
# =================================================
if __name__ == "__main__":
    app.run(debug=True)