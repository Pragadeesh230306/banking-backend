from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
DB = "banking.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- LOAN REQUEST WITH TIER RULE ----------------
@app.route("/loan/request", methods=["POST"])
def loan_request():
    data = request.get_json()

    acc_no = data["account_number"]
    amount = float(data["loan_amount"])
    tenure = int(data["tenure_months"])

    conn = get_db()
    cursor = conn.cursor()

    # get account + tier
    cursor.execute("SELECT * FROM accounts WHERE account_number=?", (acc_no,))
    acc = cursor.fetchone()

    if not acc:
        return jsonify({"error": "Account not found"}), 404

    tier = acc["tier"]
    limit = acc["loan_limit"]

    # check limit
    if amount > limit:
        return jsonify({
            "error": f"Loan exceeds limit for {tier} tier",
            "limit": limit
        }), 403

    # tier-based interest
    if tier == "SILVER":
        rate = 12
    elif tier == "GOLD":
        rate = 10
    elif tier == "PLATINUM":
        rate = 8
    else:
        rate = 6

    interest = (amount * rate * tenure) / 1200
    total = amount + interest
    emi = total / tenure

    due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    cursor.execute("""
        INSERT INTO loans
        (account_number, loan_amount, interest_rate, tenure_months, emi, status, remaining_amount, next_due_date)
        VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)
    """, (acc_no, amount, rate, tenure, emi, total, due_date))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Loan request created",
        "tier": tier,
        "rate": rate,
        "emi": round(emi, 2),
        "limit": limit
    })


if __name__ == "__main__":
    app.run(debug=True)


@app.route("/loan/pay-emi", methods=["POST"])
def pay_emi():
    data = request.get_json()

    loan_id = data["loan_id"]
    amount = float(data["amount"])

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM loans WHERE id=?", (loan_id,))
    loan = cursor.fetchone()

    if not loan:
        return jsonify({"error": "Loan not found"}), 404

    acc_no = loan["account_number"]
    remaining = loan["remaining_amount"]
    paid = loan["paid_amount"]

    # update payment
    new_paid = paid + amount
    new_remaining = remaining - amount

    cursor.execute("""
        UPDATE loans
        SET paid_amount=?, remaining_amount=?
        WHERE id=?
    """, (new_paid, new_remaining, loan_id))

    # if fully paid
    status = "ACTIVE"
    if new_remaining <= 0:
        status = "CLOSED"

    cursor.execute("""
        UPDATE loans
        SET status=?
        WHERE id=?
    """, (status, loan_id))

    # transaction log
    cursor.execute("""
        INSERT INTO transactions
        (from_account, to_account, amount, mode, charge, status)
        VALUES (?, ?, ?, 'LOAN_EMI', 0, 'SUCCESS')
    """, (acc_no, "BANK", amount))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "EMI paid successfully",
        "remaining": new_remaining,
        "status": status
    })


@app.route("/loan/apply-penalty", methods=["POST"])
def apply_penalty():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM loans WHERE status!='CLOSED'")
    loans = cursor.fetchall()

    result = []

    for loan in loans:
        acc_no = loan["account_number"]
        remaining = loan["remaining_amount"]
        tier = "SILVER"  # simplified (you can join accounts table)

        if tier == "SILVER":
            penalty_rate = 0.02
        elif tier == "GOLD":
            penalty_rate = 0.015
        elif tier == "PLATINUM":
            penalty_rate = 0.01
        else:
            penalty_rate = 0.005

        penalty = remaining * penalty_rate
        new_remaining = remaining + penalty

        cursor.execute("""
            UPDATE loans
            SET remaining_amount=?
            WHERE id=?
        """, (new_remaining, loan["id"]))

        cursor.execute("""
            INSERT INTO transactions
            (from_account, to_account, amount, mode, charge, status)
            VALUES (?, ?, ?, 'LOAN_PENALTY', 0, 'SUCCESS')
        """, ("BANK", acc_no, penalty))

        result.append({
            "account": acc_no,
            "penalty": penalty
        })

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Penalty applied",
        "data": result
    })

