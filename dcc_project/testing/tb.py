from flask import Flask, request, jsonify
import sqlite3
import time
from datetime import datetime

app = Flask(__name__)
DB = "banking.db"


# ---------------- DB CONNECTION ----------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


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

    cursor.execute("""
        SELECT * FROM beneficiaries WHERE account_number=?
    """, (acc_no,))

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
# 💸 SAFE TRANSFER (IMPS / NEFT / RTGS + ROLLBACK)
# =================================================
@app.route("/transfer", methods=["POST"])
def transfer_money():
    data = request.get_json()

    from_acc = data["from_account"]
    to_acc = data["to_account"]
    amount = float(data["amount"])
    mode = data["mode"]

    conn = get_db()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN TRANSACTION")

        # sender check
        cursor.execute("SELECT * FROM accounts WHERE account_number=?", (from_acc,))
        sender = cursor.fetchone()

        if not sender:
            raise Exception("Sender not found")

        # beneficiary check
        cursor.execute("SELECT * FROM beneficiaries WHERE account_number=?", (to_acc,))
        if not cursor.fetchone():
            raise Exception("Beneficiary not registered")

        # charges + rules
        charge = 0
        delay = 0

        if mode == "IMPS":
            charge = 10
        elif mode == "NEFT":
            delay = 10
        elif mode == "RTGS":
            if amount <= 200000:
                raise Exception("RTGS allowed only above 2 lakh")
            delay = 20
        else:
            raise Exception("Invalid mode")

        total = amount + charge

        if sender["balance"] < total:
            raise Exception("Insufficient balance")

        # simulate processing delay
        if delay > 0:
            time.sleep(delay)

        # debit sender
        cursor.execute("""
            UPDATE accounts
            SET balance = balance - ?
            WHERE account_number=?
        """, (total, from_acc))

        # credit receiver
        cursor.execute("""
            UPDATE accounts
            SET balance = balance + ?
            WHERE account_number=?
        """, (amount, to_acc))

        # transaction log
        cursor.execute("""
            INSERT INTO transactions
            (from_account, to_account, amount, mode, charge, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            from_acc, to_acc, amount, mode, charge,
            "SUCCESS", str(datetime.utcnow())
        ))

        conn.commit()

        return jsonify({
            "message": "Transfer successful",
            "amount": amount,
            "charge": charge,
            "mode": mode
        })

    except Exception as e:
        conn.rollback()

        cursor.execute("""
            INSERT INTO transactions
            (from_account, to_account, amount, mode, charge, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            from_acc, to_acc, amount, mode, 0,
            f"FAILED: {str(e)}",
            str(datetime.utcnow())
        ))

        conn.commit()

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
        UPDATE accounts
        SET balance = balance + ?
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

    return jsonify({
        "account": acc,
        "statement": result
    })


# =================================================
# 🚀 RUN APP
# =================================================
if __name__ == "__main__":
    app.run(debug=True)
