"""Run SQL files against DATABASE_URL, each in one transaction.

    python apply_sql.py schema.sql          # once, on an empty database
    python apply_sql.py views.sql           # after any view change; safe to re-run
"""
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / ".env")


def main(paths: list[str]) -> None:
    if not paths:
        sys.exit(__doc__)
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
    with psycopg.connect(url) as conn:
        for name in paths:
            path = Path(name) if Path(name).is_absolute() else HERE / name
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
            print(f"applied {path.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
