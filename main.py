import mysql.connector
from mysql.connector import pooling, Error
from flask import Flask, request, jsonify
from response import generate_reply
from winning import update
import requests
from reset import reset_all, send_summary_to_all_users,update_old_balance
from admin import handle_admin_command, load_config, is_admin, is_user_allowed
import json
import time
import threading
from datetime import datetime

# Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): 2025-08-14 22:34:55
# Current User's Login: Jeetujc

app = Flask(__name__)

# ------------------- MYSQL CONNECTION POOL -------------------

dbconfig = {
    "host": "localhost",
    "user": "root",
    "password": "anushka",
    "database": "betapp1",
    "port": 3306,
    "autocommit": True
}

connection_pool = None  # always define

try:
    connection_pool = pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=5,   # adjust size depending on traffic
        **dbconfig
    )
    print("✅ MySQL connection pool created")
except Exception as e:
    print(f"❌ Error creating pool: {e}")
    connection_pool = None  # safe fallback

# Wrapper so your functions can still call db.cursor()
class DBWrapper:
    def __init__(self, pool, dbconfig):
        self.pool = pool
        self.dbconfig = dbconfig

    def cursor(self, *args, **kwargs):
        conn = None
        try:
            if self.pool:
                conn = self.pool.get_connection()
                conn.ping(reconnect=True, attempts=3, delay=2)  # 🔑 force reconnect
            else:
                raise RuntimeError("Pool unavailable, reconnecting directly")
        except Exception as e:
            print(f"⚠️ Connection issue, reconnecting: {e}")
            conn = mysql.connector.connect(**self.dbconfig)

        cursor = conn.cursor(*args, **kwargs)
        cursor._conn = conn
        return cursor

    def commit(self):
        # autocommit=True, nothing needed
        pass

    def close(self):
        # pool handles cleanup
        pass

# Global db object (used everywhere else in your code)
db = DBWrapper(connection_pool, dbconfig)

# ------------------- DAILY SCHEDULER -------------------

def daily_scheduler():
    """Background scheduler for daily and weekly tasks"""
    while True:
        try:
            now = datetime.now()
            # Daily reset & summary at 00:20
            if now.hour == 0 and now.minute == 20:
                print(f"⏰ Running daily summary/reset at {now}")
                send_summary_to_all_users(db)

                # If Sunday, update old_balance before resetting
                if now.weekday() == 6:  # Sunday
                    update_old_balance(db)

                reset_all(db)
                time.sleep(60)
            time.sleep(30)
        except Exception as e:
            print(f"❌ Error in daily scheduler: {e}")
            time.sleep(60)

# ------------------- HELPERS -------------------

def clean_phone_number(phone_with_suffix):
    """Remove @c.us suffix"""
    return phone_with_suffix.replace("@c.us", "").replace("@lid","").strip()

def is_admin_user(phone_number):
    clean_number = clean_phone_number(phone_number)
    return is_admin(clean_number)

def is_allowed_user(phone_number):
    clean_number = clean_phone_number(phone_number)
    return is_user_allowed(clean_number)

pending_updates = {}  # phone_number -> {"bet_name": str, "session": str, "numbers": [int, int, int], "reply": str or None}
def confirm_update_thread(phone_number, db, update_func, send_message):
    """Threaded loop waiting for admin confirmation reply"""
    timeout = 120  # seconds
    start_time = time.time()
    while True:
        if phone_number in pending_updates:
            reply = pending_updates[phone_number].get("reply")
            if reply == "1":
                pd = pending_updates.pop(phone_number)
                result = update_func(db, pd["bet_name"], pd["session"], *pd["numbers"])
                if result:
                    send_message(phone_number, "✅ Update successful")
                else:
                    send_message(phone_number, "❌ Update failed")
                return
            elif reply == "2":
                pending_updates.pop(phone_number, None)
                send_message(phone_number, "❌ Update cancelled. Please send numbers again if needed.")
                return
        if time.time() - start_time > timeout:
            pending_updates.pop(phone_number, None)
            send_message(phone_number, "⏰ Confirmation timeout. Please send your update again.")
            return
        time.sleep(2)
# ------------------- FLASK ROUTES -------------------

@app.route("/process", methods=["POST"])
def process_message():
    data = request.get_json()
    number = data.get("number")  # "916263163540@c.u"
    message = data.get("message")
    replied_msg = data.get("replied_message")
    clean_number = clean_phone_number(number)

    print(f"Received message from {number}: {message}")

    # Check if user is allowed
    if(message.lower().startswith("getid")):
        clean_number = clean_phone_number(number)
        return jsonify({"reply": f"Your ID: {clean_number}"}), 200
    if not is_allowed_user(number):
        print(f"User {number} not allowed")
        return jsonify({"reply": ""}), 200
    if is_admin_user(number) and clean_number in pending_updates and pending_updates[clean_number]["reply"] is None:
        if message.strip() in ("1", "2"):
            pending_updates[clean_number]["reply"] = message.strip()
            return jsonify({"reply": "⏳ Confirmation received. Processing..."})
        else:
            return jsonify({"reply": "❓ Please reply with 1 to CONFIRM or 2 to CANCEL."})
    # Admin handling
    if is_admin_user(number):
        clean_number = clean_phone_number(number)
        if not message.lower().startswith("update"):
            clean_number = clean_phone_number(number)
            admin_reply = handle_admin_command(clean_number, message, db)
            if admin_reply:
                return jsonify({"reply": admin_reply}), 200

        if is_admin_user(number) and message.lower().startswith("update"):
            try:
                lines = message.strip().split('\n')
                if len(lines) >= 3:
                    bet_info = lines[1].strip().split()
                    bet_name = bet_info[0].upper()
                    session = bet_info[1].upper()
                    numbers = list(map(int, lines[2].strip().split()))
                    if len(numbers) == 3:
                        pending_updates[clean_number] = {
                            "bet_name": bet_name,
                            "session": session,
                            "numbers": numbers,
                            "reply": None
                        }
                        threading.Thread(
                            target=confirm_update_thread,
                            args=(clean_number, db, update, send_message),
                            daemon=True
                        ).start()
                        return jsonify({"reply": (
                            f"🚦 *Confirm Update*\n"
                            f"Event: {bet_name} {session}\n"
                            f"Numbers: {numbers[0]}, {numbers[1]}, {numbers[2]}\n\n"
                            f"Reply with:\n"
                            f"1 to CONFIRM\n"
                            f"2 to CANCEL\n"
                        )}), 200
                return jsonify({"reply": "❌ Invalid format"}), 200
            except Exception as e:
                print(f"Update error: {e}")
                return jsonify({"reply": "❌ Update failed"}), 200


    # Regular user
    clean_number = clean_phone_number(number)
    reply = generate_reply(clean_number, message, db, replied_msg)
    return jsonify({"reply": reply}), 200

# ------------------- WHATSAPP MESSAGE SENDER -------------------

def send_message(phone_number, message):
    """Send message via WhatsApp"""
    try:
        response = requests.post('http://localhost:3003/send-message', json={
            'number': phone_number,
            'message': message
        })

        if response.status_code == 200:
            print(f"✅ Message sent to {phone_number}")
            return True
        else:
            print(f"❌ Failed to send message to {phone_number}")
            return False

    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False

# ------------------- MAIN ENTRY -------------------

if __name__ == "__main__":
    # Start daily scheduler in background
    scheduler_thread = threading.Thread(target=daily_scheduler, daemon=True)
    scheduler_thread.start()

    # Start Flask app
    app.run(port=5002)
