from flask import Flask, request, jsonify
import sqlite3
import random

app = Flask(__name__)

# ---------------- DB CONNECTION ----------------
def get_db():
    conn = sqlite3.connect("banking.db")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- REGISTER API ----------------
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()

        name = data.get("name")
        email = data.get("email")
        phone = data.get("phone")

        if not name or not email or not phone:
            return jsonify({"error": "All fields are required"}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Insert user
        cursor.execute("""
        INSERT INTO users (name, email, phone, role, status, created_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (name, email, phone, "CUSTOMER", "INACTIVE"))

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

        return jsonify({
            "message": "Registration successful",
            "user_id": user_id
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- APPROVE USER API ----------------
@app.route('/approve/<int:user_id>', methods=['POST'])
def approve(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check user
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Update KYC
        cursor.execute("""
        UPDATE kyc_verification
        SET status = 'APPROVED'
        WHERE user_id = ?
        """, (user_id,))

        # Activate user
        cursor.execute("""
        UPDATE users
        SET status = 'ACTIVE'
        WHERE user_id = ?
        """, (user_id,))

        # Generate account number
        account_number = str(random.randint(1000000000, 9999999999))

        # Create account
        cursor.execute("""
        INSERT INTO accounts (
            user_id,
            account_number,
            account_type,
            account_tier,
            balance,
            interest_rate,
            status,
            created_at
        )
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

        # Notification
        cursor.execute("""
        INSERT INTO notifications (user_id, message, type, status, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            user_id,
            "Your account has been approved and created",
            "SUCCESS",
            "UNREAD"
        ))

        conn.commit()
        conn.close()

        return jsonify({
            "message": "User approved successfully",
            "account_number": account_number
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- ACCOUNT DETAILS API ----------------
@app.route('/account/<int:user_id>', methods=['GET'])
def get_account(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT account_number, account_type, account_tier, balance, interest_rate, status
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
            "account_tier": account["account_tier"],
            "balance": account["balance"],
            "interest_rate": account["interest_rate"],
            "status": account["status"]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- RUN SERVER ----------------
if __name__ == '__main__':
    app.run(debug=True)

