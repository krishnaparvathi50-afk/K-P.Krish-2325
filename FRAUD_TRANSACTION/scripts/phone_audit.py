#!/usr/bin/env python3
import argparse
import sqlite3
import csv
import re
from pathlib import Path


def normalize_phone(number: str) -> str:
    if not number:
        return ""
    raw = str(number).strip()
    cleaned = re.sub(r"[\s\-()]+", "", raw)
    if re.search(r"[^0-9+]", cleaned):
        return ""
    if not cleaned.startswith("+") and cleaned.isdigit():
        cleaned = "+" + cleaned
    return cleaned


def looks_masked(number: str) -> bool:
    if not number:
        return True
    return bool(re.search(r"[xX*]", number)) or bool(re.search(r"[^0-9+\-()\s]", number))


def scan_db(db_path: Path, apply: bool = False):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Check for users table
    try:
        cur.execute("SELECT id, username, mobile FROM users")
        rows = cur.fetchall()
    except Exception as e:
        print("Failed to query users table:", e)
        conn.close()
        return 1

    report = []
    fixes = []
    for r in rows:
        uid, username, mobile = r
        mobile_str = mobile or ""
        normalized = normalize_phone(mobile_str)
        masked = looks_masked(mobile_str)
        status = "ok" if normalized else "invalid"
        if masked:
            status = "masked"
        report.append((uid, username, mobile_str, normalized, status))
        if apply and status == "invalid" and mobile_str.isdigit():
            new = "+" + mobile_str
            fixes.append((new, uid))

    # Write CSV
    out_path = Path("phone_audit_report.csv")
    with out_path.open("w", newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["id", "username", "mobile", "normalized", "status"]) 
        for row in report:
            w.writerow(row)

    print(f"Scanned {len(rows)} users. Report written to {out_path.resolve()}")
    counts = {"ok":0, "invalid":0, "masked":0}
    for _,_,_,_,status in report:
        counts[status] = counts.get(status,0) + 1
    print("Summary:", counts)

    if apply and fixes:
        print(f"Applying {len(fixes)} simple fixes (adding leading '+')...")
        for new, uid in fixes:
            cur.execute("UPDATE users SET mobile=? WHERE id=?", (new, uid))
        conn.commit()
        print("Applied fixes.")

    conn.close()
    return 0


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument("--db", help="Path to SQLite database file", default="database.db")
    p.add_argument("--apply", help="Apply simple fixes (add leading + to numeric-only mobiles)", action="store_true")
    args = p.parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print("DB not found:", db_path)
        exit(2)
    exit(scan_db(db_path, apply=args.apply))
