import sqlite3
import tempfile
from pathlib import Path
import subprocess
import os


def setup_db_from_init(db_path: str, repo_root: Path):
    # create a fresh DB from db/init.sql
    sql = (repo_root / "db" / "init.sql").read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(sql)
    conn.commit()
    conn.close()


def test_migration_adds_strict_column(tmp_path: Path):
    # repo root is one level up from tests/ (parents[1])
    repo_root = Path(__file__).resolve().parents[1]
    db_file = tmp_path / "app.sqlite"
    setup_db_from_init(str(db_file), repo_root)

    # run migration runner with APP_DB_PATH pointed to our temp DB
    env = os.environ.copy()
    env["APP_DB_PATH"] = str(db_file)
    runner = repo_root / "scripts" / "run_migrations.py"
    subprocess.check_call(["python", str(runner)], env=env)

    # verify column exists
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(partner)")
    cols = [r[1] for r in cur.fetchall()]
    conn.close()
    assert "strict" in cols
