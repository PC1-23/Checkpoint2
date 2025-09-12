from __future__ import annotations

import os
from pathlib import Path

from .dao import get_connection


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = os.environ.get("APP_DB_PATH", str(ROOT / "app.sqlite"))
INIT_SQL = ROOT / "db" / "init.sql"


def init_db(db_path: str = DEFAULT_DB_PATH) -> str:
	"""Create/connect to a persistent SQLite DB file and apply schema.

	Ensures data persists across restarts. Expects Partner A to add their
	user/product schema to db/init.sql as well. This will be idempotent.
	"""
	Path(db_path).parent.mkdir(parents=True, exist_ok=True)
	conn = get_connection(db_path)
	try:
		if INIT_SQL.exists():
			with open(INIT_SQL, "r", encoding="utf-8") as f:
				sql = f.read()
			if sql.strip():
				conn.executescript(sql)
				conn.commit()
	finally:
		conn.close()
	return db_path


if __name__ == "__main__":
	path = init_db()
	print(f"Initialized SQLite DB at: {path}")
	print("Set APP_DB_PATH to override location.")

