from flask import Flask, render_template, request, jsonify
import sqlite3
from pathlib import Path
from model import predict_fraud

app = Flask(__name__)
app.secret_key = "secret"

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ROOT_DB = ROOT_DIR / "database.db"
LEGACY_DB = BASE_DIR / "database.db"
DB_PATH = ROOT_DB if ROOT_DB.exists() else LEGACY_DB

def get_db():
    return sqlite3.connect(str(DB_PATH))


def table_has_column(cur, table, column):
    """Return True if the specified column exists in the table."""
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def classify_ml(*, risk):
    """Map numeric risk score to human-readable ML verdict."""
    if risk is None:
        return "UNKNOWN"
    if risk >= 85:
        return "HIGH"
    if risk >= 50:
        return "MEDIUM"
    return "LOW"


def fetch_transactions(*, show_all=False, limit=50, offset=0):
    """Fetch transactions with optional pagination and graceful risk fallback."""
    db = get_db()
    cur = db.cursor()
    has_risk = table_has_column(cur, "transactions", "risk")
    risk_expr = "risk" if has_risk else "NULL AS risk"
    query = f"SELECT sender,receiver,amount,ip,timestamp,status,{risk_expr} FROM transactions ORDER BY id DESC"
    params = []
    if not show_all and limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    if offset:
        query += " OFFSET ?"
        params.append(offset)
    cur.execute(query, params)
    rows = cur.fetchall()

    registered_cache: dict[str, bool] = {}

    def is_registered(mobile: str) -> bool:
        if mobile in registered_cache:
            return registered_cache[mobile]
        cur.execute("SELECT 1 FROM users WHERE mobile=? LIMIT 1", (mobile,))
        registered_cache[mobile] = cur.fetchone() is not None
        return registered_cache[mobile]

    transactions = []
    for sender, receiver, amount, ip, timestamp, status, risk in rows:
        if risk is None:
            try:
                _, risk = predict_fraud(amount)
            except Exception:
                risk = None

        receiver_registered = is_registered(receiver)

        # Sending to an unregistered receiver is always treated as fraud.
        if not receiver_registered:
            status_display = "FRAUD"
            if risk is None or risk < 85:
                risk = 85.0
        else:
            status_display = status

        ml_label = classify_ml(risk=risk)

        transactions.append(
            dict(
                sender=sender,
                receiver=receiver,
                amount=amount,
                ip=ip,
                timestamp=timestamp,
                status=status_display,
                risk=risk,
                ml_label=ml_label,
            )
        )

    db.close()
    return transactions


def init_db():
    db = get_db()
    cur = db.cursor()

    # Create users table if missing
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        mobile TEXT UNIQUE,
        is_blocked INTEGER DEFAULT 0
    )
    """)

    # Create transactions table if missing
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        receiver TEXT,
        amount REAL,
        ip TEXT,
        timestamp TEXT,
        status TEXT,
        risk REAL
    )
    """)

    db.commit()

    # Populate sample users if table empty
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    if count == 0:
        sample_users = [f"user{i}" for i in range(1, 51)]
        for i, u in enumerate(sample_users):
            mobile = str(6000000000 + i)
            try:
                cur.execute("INSERT INTO users (username, mobile, is_blocked) VALUES (?,?,0)", (u, mobile))
            except sqlite3.IntegrityError:
                pass
        db.commit()

    db.close()

# ---------------- HOME → TRANSACTION PAGE ----------------
@app.route('/')
def transaction():
    show_all = request.args.get('all') == '1'
    transactions = fetch_transactions(show_all=show_all, limit=50)
    return render_template("transaction.html", transactions=transactions)


@app.route('/transactions')
def transactions_api():
    """JSON endpoint to return transactions with offset/limit for 'Load more' support."""
    try:
        offset = int(request.args.get('offset', 0))
    except ValueError:
        offset = 0
    try:
        limit = int(request.args.get('limit', 50))
    except ValueError:
        limit = 50

    transactions = fetch_transactions(show_all=False, limit=limit, offset=offset)
    return jsonify(transactions)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=8000, use_reloader=False)
