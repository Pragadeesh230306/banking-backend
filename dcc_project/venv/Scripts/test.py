from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

DB = "banking.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- GET ACCOUNT (AFTER LOGIN ONLY) ----------------
@app.route("/my-account", methods=["POST"])
def my_account():
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "Login required"}), 401

    conn = get_db()
    cursor = conn.cursor()

    # get account using user_id
    cursor.execute("""
        SELECT account_number, account_type, balance, status, created_at
        FROM accounts
        WHERE user_id = ?
    """, (user_id,))

    account = cursor.fetchone()
    conn.close()

    if not account:
        return jsonify({"error": "Account not found"}), 404

    return jsonify({
        "account_number": account["account_number"],
        "account_type": account["account_type"],
        "balance": account["balance"],
        "status": account["status"],
        "created_at": account["created_at"]
    })


if __name__ == "__main__":
    app.run(debug=True)


from flask import Flask, jsonify
import sqlite3

app = Flask(__name__)
DB = "banking.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- TIER INTEREST SYSTEM ----------------
@app.route("/run-tier-interest", methods=["POST"])
def run_tier_interest():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT account_number, balance, tier FROM accounts")
    accounts = cursor.fetchall()

    result = []

    for acc in accounts:
        acc_no = acc["account_number"]
        balance = acc["balance"]
        tier = acc["tier"]

        # 💡 Tier-based interest rates
        if tier == "SILVER":
            rate = 0.0001   # 0.01%
        elif tier == "GOLD":
            rate = 0.0002   # 0.02%
        elif tier == "PLATINUM":
            rate = 0.0003   # 0.03%
        elif tier == "DIAMOND":
            rate = 0.0005   # 0.05%
        else:
            rate = 0.0001   # default

        interest = balance * rate
        new_balance = balance + interest

        # update balance
        cursor.execute("""
            UPDATE accounts
            SET balance = ?
            WHERE account_number = ?
        """, (new_balance, acc_no))

        # log transaction
        cursor.execute("""
            INSERT INTO transactions
            (from_account, to_account, amount, mode, charge, status)
            VALUES (?, ?, ?, 'INTEREST', 0, 'SUCCESS')
        """, ("BANK", acc_no, interest))

        result.append({
            "account": acc_no,
            "tier": tier,
            "interest_added": round(interest, 2),
            "new_balance": round(new_balance, 2)
        })

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Tier-based interest applied successfully",
        "data": result
    })


if __name__ == "__main__":
    app.run(debug=True)