import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "database.db"


def init_database():
	conn = sqlite3.connect(str(DB_PATH))
	cur = conn.cursor()

	cur.execute("DROP TABLE IF EXISTS users")
	cur.execute(
		"""
		CREATE TABLE users(
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT UNIQUE,
			email TEXT UNIQUE,
			mobile TEXT UNIQUE,
			password TEXT
		)
		"""
	)

	cur.execute(
		"""
		CREATE TABLE IF NOT EXISTS transactions(
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			sender TEXT,
			receiver TEXT,
			amount REAL,
			ip TEXT,
			timestamp TEXT,
			status TEXT
		)
		"""
	)

	conn.commit()
	conn.close()
	print(f"Database initialized at: {DB_PATH}")


if __name__ == "__main__":
	init_database()
