from flask import Flask, request, jsonify
import sqlite3
import random
from datetime import datetime, timedelta

app = Flask(__name__)
DB = "banking.db"


# ---------------- DB CONNECTION ----------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- FORGOT PASSWORD (OTP GENERATION) ----------------
@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()

    account_no = data["account_number"]
    mobile = data["mobile"]
    email = data["email"]

    conn = get_db()
    cursor = conn.cursor()

    # 🔐 verify identity
    cursor.execute("""
        SELECT * FROM users
        WHERE account_number=? AND mobile=? AND email=?
    """, (account_no, mobile, email))

    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "Invalid account details"}), 401

    # 🔑 generate OTP
    otp = str(random.randint(100000, 999999))

    expiry_time = datetime.now() + timedelta(minutes=5)
    expiry_str = expiry_time.strftime("%Y-%m-%d %H:%M:%S")

    # 💾 store OTP
    cursor.execute("""
        UPDATE users
        SET reset_otp=?, otp_expiry=?
        WHERE account_number=?
    """, (otp, expiry_str, account_no))

    conn.commit()
    conn.close()

    # 📲 simulate SMS + Email
    print(f"[SMS] OTP for {mobile}: {otp}")
    print(f"[EMAIL] OTP sent to {email}: {otp}")

    return jsonify({
        "message": "OTP sent successfully",
        "validity": "5 minutes"
    })


# ---------------- RESET PASSWORD ----------------
@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()

    account_no = data["account_number"]
    otp_input = data["otp"]
    new_password = data["new_password"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM users WHERE account_number=?
    """, (account_no,))

    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "Account not found"}), 404

    # ❌ OTP check
    if user["reset_otp"] != otp_input:
        return jsonify({"error": "Invalid OTP"}), 400

    # ⏳ expiry check
    if not user["otp_expiry"]:
        return jsonify({"error": "OTP not generated"}), 400

    now = datetime.now()
    expiry = datetime.strptime(user["otp_expiry"], "%Y-%m-%d %H:%M:%S")

    if now > expiry:
        return jsonify({"error": "OTP expired"}), 400

    # 🔐 update password
    cursor.execute("""
        UPDATE users
        SET password=?, reset_otp=NULL, otp_expiry=NULL
        WHERE account_number=?
    """, (new_password, account_no))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Password reset successful"
    })


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)