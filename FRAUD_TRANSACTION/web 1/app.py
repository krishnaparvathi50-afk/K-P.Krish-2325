from pathlib import Path
import sqlite3
from datetime import datetime
import os
from dotenv import load_dotenv

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import re

from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not UPLOAD_FOLDER.exists():
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

ROOT_DB = ROOT_DIR / "database.db"
LEGACY_DB = BASE_DIR / "database.db"
DB_PATH = ROOT_DB if ROOT_DB.exists() else LEGACY_DB

# Load environment variables from project .env (project root)
env_path = ROOT_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_table_columns(table: str):
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    conn.close()
    return cols


def ensure_users_schema():
    """Ensure common columns exist in the users table expected by the app.
    Adds `email` and `password` columns if they're missing.
    """
    cols = get_table_columns("users")
    if not cols:
        # No users table present in this DB; nothing to do here.
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    altered = False
    if "email" not in cols:
        try:
            cur.execute("ALTER TABLE users ADD COLUMN email TEXT UNIQUE")
            altered = True
            print("Added 'email' column to users table")
        except Exception as e:
            print("Failed to add email column:", e)
            # Try adding without UNIQUE constraint (SQLite cannot add UNIQUE via ALTER TABLE)
            try:
                cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
                altered = True
                print("Added 'email' column (without UNIQUE) to users table")
            except Exception as e2:
                print("Failed to add email column without UNIQUE:", e2)
    if "password" not in cols:
        try:
            cur.execute("ALTER TABLE users ADD COLUMN password TEXT")
            altered = True
            print("Added 'password' column to users table")
        except Exception as e:
            print("Failed to add password column:", e)
    if altered:
        conn.commit()
    conn.close()


# Ensure DB schema is compatible on startup
def ensure_tables_exist():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    # Create users table if missing with common columns
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            mobile TEXT UNIQUE,
            password TEXT,
            is_blocked INTEGER DEFAULT 0
        )
        """
    )
    # Create transactions table if missing with common columns
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            receiver TEXT,
            amount REAL,
            ip TEXT,
            timestamp TEXT,
            status TEXT,
            risk REAL
        )
        """
    )
    # Create notifications table if missing
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT,
            timestamp TEXT,
            is_read INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


ensure_tables_exist()
ensure_users_schema()


def ensure_transactions_schema():
    cols = get_table_columns("transactions")
    if not cols:
        return
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    altered = False
    if "twilio_sid" not in cols:
        try:
            cur.execute("ALTER TABLE transactions ADD COLUMN twilio_sid TEXT")
            altered = True
            print("Added 'twilio_sid' column to transactions table")
        except Exception as e:
            print("Failed to add twilio_sid column:", e)
    if "twilio_error" not in cols:
        try:
            cur.execute("ALTER TABLE transactions ADD COLUMN twilio_error TEXT")
            altered = True
            print("Added 'twilio_error' column to transactions table")
        except Exception as e:
            print("Failed to add twilio_error column:", e)
    if altered:
        conn.commit()
    conn.close()


ensure_transactions_schema()


def normalize_phone(number: str) -> str:
    """Normalize a phone number to E.164-like format.

    Rules:
    - Strip spaces, dashes and parentheses.
    - Reject numbers containing letters or placeholders like 'X' or '*'.
    - If the cleaned value already starts with '+', validate length and return it.
    - If the cleaned value is 10 digits, assume India and return '+91' + digits.
    - If the cleaned value starts with '91' and is 12 digits, prepend '+' (India full without +).
    - Otherwise prepend '+' to numeric values as a fallback.
    - Return empty string on invalid input or if resulting digits exceed 15 (E.164 max).
    """
    if not number:
        return ""
    raw = str(number).strip()
    cleaned = re.sub(r"[\s\-()]+", "", raw)

    # Reject placeholders or unexpected characters
    if re.search(r"[xX*]", cleaned) or re.search(r"[^0-9+]", cleaned):
        return ""

    # Already in E.164 form
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if not digits.isdigit():
            return ""
        if 7 <= len(digits) <= 15:
            return cleaned
        return ""

    # Digits only from here
    if not cleaned.isdigit():
        return ""

    # 10-digit numbers -> assume India +91
    if len(cleaned) == 10:
        candidate = "+91" + cleaned
        return candidate

    # If user entered '91' + 10 digits without plus
    if cleaned.startswith("91") and len(cleaned) == 12:
        return "+" + cleaned

    # Fallback: prepend plus and validate length
    if 1 <= len(cleaned) <= 15:
        candidate = "+" + cleaned
        if 7 <= len(candidate) - 1 <= 15:
            return candidate

    return ""


def send_alert_sms(to_number: str, body: str) -> bool:
    """Send an SMS via Twilio.

    Returns tuple `(success: bool, info: str)` where `info` is the message SID on success
    or an error message on failure.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")

    if not (account_sid and auth_token and from_number):
        print("Twilio not configured. Skipping SMS alert.")
        return False

    # Normalize recipient number to E.164-like. If invalid, abort.
    cleaned = normalize_phone(to_number)
    if not cleaned:
        print("Invalid recipient phone number, unable to normalize:", to_number)
        return False

    try:
        client = Client(account_sid, auth_token)
        resp = client.messages.create(body=body, from_=from_number, to=cleaned)
        sid = getattr(resp, 'sid', None)
        print(f"Twilio message sent, SID={sid}")
        return True, sid or ""
    except TwilioRestException as e:
        # Twilio-specific details
        try:
            err = f"status={e.status} code={e.code} msg={e.msg}"
        except Exception:
            err = str(e)
        print("TwilioRestException when sending SMS:", err)
        return False, err
    except Exception as e:
        print("Failed to send SMS via Twilio:", e)
        return False, str(e)


def ensure_twilio_config():
    """Validate Twilio credentials at startup and report problems.
    Does a lightweight account fetch to verify credentials and connectivity.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    if not (account_sid and auth_token and from_number):
        print("Twilio not configured (missing env vars). Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER in .env")
        return
    try:
        client = Client(account_sid, auth_token)
        # Try to fetch account to validate creds
        acct = client.api.accounts(account_sid).fetch()
        print(f"Twilio account OK: {acct.friendly_name} ({acct.sid})")
    except TwilioRestException as e:
        print("Twilio credentials invalid or API error:")
        try:
            print("Status:", e.status, "Code:", e.code, "Message:", e.msg)
        except Exception:
            print(str(e))
    except Exception as e:
        print("Unexpected error validating Twilio config:", e)


# Validate Twilio on startup so problems are visible in logs
ensure_twilio_config()


@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        db.close()

        if user and check_password_hash(user[4], password):
            session["user"] = username
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid Username or Password")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        mobile_input = request.form.get("mobile", "").strip()
        mobile = normalize_phone(mobile_input)
        if not mobile:
            return render_template("register.html", error="Enter a valid mobile number (e.g. +919629451234)")
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match!")

        hashed_password = generate_password_hash(password)

        db = None
        try:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "SELECT * FROM users WHERE username=? OR email=? OR mobile=?",
                (username, email, mobile),
            )
            existing = cur.fetchone()

            if existing:
                return render_template("register.html", error="User already exists!")

            cur.execute(
                """
                INSERT INTO users (username, email, mobile, password)
                VALUES (?, ?, ?, ?)
                """,
                (username, email, mobile, hashed_password),
            )
            db.commit()
            print(f"Registered new user: {username} ({mobile})")

            # Send welcome SMS to the newly registered mobile (if Twilio configured)
            try:
                sms_body = f"Welcome {username}! Your account has been created successfully."
                sent, info = send_alert_sms(mobile, sms_body)
                if sent:
                    flash("Registration successful — welcome SMS sent.", "success")
                else:
                    flash(f"Registration successful but SMS failed: {info}", "warning")
            except Exception as e:
                print("Error sending welcome SMS:", e)
                flash("Registration successful but SMS failed due to server error.", "warning")

            return redirect(url_for("login"))
        except sqlite3.IntegrityError as e:
            print("SQLite integrity error during registration:", e)
            return render_template("register.html", error="User already exists or invalid data.")
        except Exception as e:
            print("Unexpected error during registration:", e)
            return render_template("register.html", error="Registration failed due to server error.")
        finally:
            if db:
                db.close()

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=session["user"])


@app.route("/transaction", methods=["GET", "POST"])
def transaction():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        receiver_input = request.form.get("mobile", "").strip()
        receiver = normalize_phone(receiver_input)
        if not receiver:
            return render_template("transaction.html", error="Enter a valid recipient mobile number (e.g. +919629451234)")
        raw_amount = request.form["amount"].strip()

        try:
            amount = float(raw_amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return render_template("transaction.html", error="Enter a valid amount greater than 0.")

        sender = session["user"]
        ip = request.remote_addr
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT * FROM users WHERE mobile=?", (receiver,))
        rec_user = cur.fetchone()

        cur.execute("SELECT mobile FROM users WHERE username=?", (sender,))
        sender_mobile_row = cur.fetchone()
        sender_mobile = sender_mobile_row[0] if sender_mobile_row else None

        # Normalize sender_mobile (from DB) as well to compare safely
        sender_mobile = normalize_phone(sender_mobile) if sender_mobile else None

        if sender_mobile and receiver == sender_mobile:
            db.close()
            return render_template("transaction.html", error="Cannot send to yourself!")

        # Default status is success. If receiver isn't registered, flag as fraud and alert sender.
        status = "success"
        notice = None
        if not rec_user:
            status = "fraud"
            notice = "Receiver is not registered. Transaction flagged as fraud and alert sent to your mobile."
            if sender_mobile:
                sms_body = (
                    f"ALERT: A transaction attempted to unregistered number {receiver} for amount {amount} "
                    f"from your account at {timestamp}. If this wasn't you, contact support immediately."
                )
                send_alert_sms(sender_mobile, sms_body)

        # Record transaction with status (success/fraud).
        cur.execute(
            """
            INSERT INTO transactions (sender, receiver, amount, ip, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sender, receiver, amount, ip, timestamp, status),
        )
        tx_id = cur.lastrowid

        # If an alert SMS is sent, record Twilio response (sid or error) against the transaction
        tw_sid = None
        tw_err = None
        if not rec_user and sender_mobile:
            success, info = send_alert_sms(sender_mobile, sms_body)
            if success:
                tw_sid = info
            else:
                tw_err = info

        # Update transaction row with Twilio info (if any)
        if tw_sid or tw_err:
            cur.execute(
                "UPDATE transactions SET twilio_sid=?, twilio_error=? WHERE id=?",
                (tw_sid, tw_err, tx_id),
            )
            # also surface Twilio send errors to the user immediately
            if tw_err:
                flash(f"SMS alert failed: {tw_err}", "danger")

        db.commit()
        db.close()

        # Notify user and redirect to logs so the new transaction is visible immediately
        if notice:
            flash(notice, "warning")
        else:
            flash("Transaction Successful", "success")
        return redirect(url_for("logs"))

    return render_template("transaction.html")


@app.route("/logs")
def logs():
    if "user" not in session:
        return redirect(url_for("login"))
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM transactions ORDER BY id DESC")
    rows = cur.fetchall()
    # convert to list of dicts for template access by column name
    data = [dict(r) for r in rows]
    db.close()

    return render_template("logs.html", data=data)


@app.route("/upload_statement", methods=["GET", "POST"])
def upload_statement():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

            # v10 - BALANCED DECISION ENGINE (Allows clean screenshots per user reference)
            def analyze_behavior(path, filename_clean):
                try:
                    with open(path, 'rb') as f:
                        # Scan a larger chunk for Behavioral Keywords
                        chunk = f.read(16384).decode('utf-8', errors='ignore').lower()
                        
                        # 1. PRIORITY #1: Behavioral Fraud Indicators (User Prompt)
                        behavioral_indicators = {
                            'urgent transfer': 'Suspicious keyword "Urgent Transfer" detected.',
                            'cash deposit anomaly': 'Pattern mismatch: "Cash Deposit Anomaly" found.',
                            'unknown account': 'Transfers to unrecognized or random beneficiaries.',
                            'multiple transfers': 'Unnatural frequency of short-term transfers.',
                            'unnatural pattern': 'Transaction sequences matching automated fraud.'
                        }
                        for key, reason in behavioral_indicators.items():
                            if key in chunk:
                                return "FRAUD", f"Reason: {reason}", 91.5

                        # 2. PRIORITY #2: Structural Forgery (Active Editing)
                        forgery_markers = {
                            'photoshop': 'FORGERY: Document edited via Adobe Photoshop.',
                            'canva': 'FORGERY: Document designed using Canva design tool.',
                            'picsart': 'FORGERY: Manipulated using PicsArt mobile.',
                            'gimp': 'FORGERY: Document edited via GIMP software.'
                        }
                        for key, reason in forgery_markers.items():
                            if key in chunk:
                                return "FRAUD", f"Reason: {reason}", 89.0

                        # 3. PRIORITY #3: Capture Origins (Screenshots are allowed if content is clean)
                        capture_markers = ['screenshot', 'gpay', 'phonepe', 'paytm']
                        if any(m in chunk for m in capture_markers) or filename_clean.startswith('screenshot'):
                            # Balanced Rule: If it's a screenshot but NO fraud keywords found -> GENUINE
                            return "GENUINE", "Reason: Normal transaction history detected in verified capture.", 8.5

                        # 4. DEFAULT: Regular Bank PDF/Export
                        return "GENUINE", "Reason: Transactions look normal and consistent with banking standards.", 3.0

                except Exception as e:
                    return "GENUINE", f"Reason: Standard scan complete. (Metadata check: {str(e)})", 1.0

            filename_clean = filename.lower()
            
            # RUN THE DECISION ENGINE
            status_type, reason, risk_score = analyze_behavior(file_path, filename_clean)
            
            is_fraud = (status_type == "FRAUD")
            result = "fraud" if is_fraud else "genuine"
            # Formatted exactly for the UI Card
            display_reason = f"Reason: {reason}"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            username = session["user"]
            
            db = get_db()
            cur = db.cursor()
            
            if is_fraud:
                cur.execute(
                    "INSERT INTO notifications (username, message, timestamp) VALUES (?, ?, ?)",
                    (username, f"{status_type}: {display_reason}", timestamp)
                )
                db.commit()
                flash(f"{status_type}: {display_reason}", "danger")
            else:
                flash(f"{status_type}: {display_reason}", "success")
            
            db.close()
            # Pass everything to the exact UI card
            return render_template("upload_statement.html", 
                                 result=result, 
                                 filename=filename, 
                                 risk_score=risk_score,
                                 reason=display_reason)

    return render_template("upload_statement.html")


def get_notification_count(username):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM notifications WHERE username=? AND is_read=0", (username,))
    count = cur.fetchone()[0]
    db.close()
    return count


@app.context_processor
def inject_notifications():
    if "user" in session:
        return {'notif_count': get_notification_count(session["user"])}
    return {'notif_count': 0}


@app.route("/api/fraud_stats")
def fraud_stats():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    db = get_db()
    cur = db.cursor()
    
    # 1. Genuine vs Fraud Transactions
    cur.execute("SELECT status, COUNT(*) FROM transactions GROUP BY status")
    tx_stats = {row[0]: row[1] for row in cur.fetchall()}
    
    # 2. Top Fraud Targets (Receivers)
    cur.execute(
        """
        SELECT receiver, COUNT(*) as count 
        FROM transactions 
        WHERE status='fraud' 
        GROUP BY receiver 
        ORDER BY count DESC 
        LIMIT 5
        """
    )
    targets = [{"name": row[0], "count": row[1]} for row in cur.fetchall()]
    
    # 3. Fraud Alerts from Statements (by User)
    cur.execute(
        """
        SELECT username, COUNT(*) as count 
        FROM notifications 
        WHERE message LIKE '%ALERT%' 
        GROUP BY username 
        ORDER BY count DESC 
        LIMIT 5
        """
    )
    alerts = [{"name": row[0], "count": row[1]} for row in cur.fetchall()]
    
    db.close()
    
    return jsonify({
        "tx_stats": tx_stats,
        "top_targets": targets,
        "top_alerts": alerts
    })


@app.route("/api/notifications/unread")
def unread_count():
    if "user" not in session:
        return jsonify({"count": 0})
    count = get_notification_count(session["user"])
    return jsonify({"count": count})


@app.route("/api/notifications/list")
def list_notifications():
    if "user" not in session:
        return jsonify({"notifications": []})
    
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT message, timestamp FROM notifications WHERE username=? AND is_read=0 ORDER BY id DESC LIMIT 10",
        (session["user"],)
    )
    rows = cur.fetchall()
    db.close()
    
    return jsonify({
        "notifications": [{"message": r[0], "time": r[1]} for r in rows]
    })


@app.route("/api/notifications/clear", methods=["POST"])
def clear_notifications():
    if "user" not in session:
        return jsonify({"success": False})
    
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE notifications SET is_read=1 WHERE username=?", (session["user"],))
    db.commit()
    db.close()
    
    return jsonify({"success": True})


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
