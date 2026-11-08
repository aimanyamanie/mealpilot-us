"""Run a .sql file against DATABASE_URL in one transaction.

    python apply_sql.py schema.sql     # once, on an empty database
    python apply_sql.py views.sql      # after any view change; safe to re-run
"""
import sys
from pathlib import Path

from db import connect

with connect() as conn:
    conn.execute(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("applied", sys.argv[1])
