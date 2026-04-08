from flask import Flask, request, jsonify
from flask_mail import Mail, Message
import random
from datetime import datetime, timedelta

app = Flask(__name__)

# ---------------- DB CONNECTION ----------------
def get_db():
    conn = sqlite3.connect("banking.db")
    conn.row_factory = sqlite3.Row
    return conn

# ================= EMAIL CONFIG =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'pragdeezzh230306@gmail.com'
app.config['MAIL_PASSWORD'] = 'nzuu zcih rcsi omqh'

mail = Mail(app)

otp_store = {}

daily_limit = {}

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

@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    email = data["email"]

    # limit check
    if not check_limit(email):
        return jsonify({"error": "Daily OTP limit reached (5 per day)"}), 400

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

    return jsonify({"message": "OTP sent successfully"})

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

    # OTP used → remove it (important banking rule)
    del otp_store[email]

    return jsonify({"message": "OTP verified successfully"})

@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    data = request.get_json()
    email = data["email"]

    if not check_limit(email):
        return jsonify({"error": "Daily OTP limit reached (5 per day)"}), 400

    otp = str(random.randint(100000, 999999))

    otp_store[email] = {
        "otp": otp,
        "expiry": datetime.utcnow() + timedelta(minutes=5)
    }

    msg = Message(
        subject="Resent Bank OTP",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )

    msg.body = f"Your NEW OTP is {otp}. Valid for 5 minutes."

    mail.send(msg)

    return jsonify({"message": "OTP resent successfully"})
                   
if __name__ == "__main__":
    app.run(debug=True)