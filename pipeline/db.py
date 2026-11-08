"""Settings from .env (repo root) and a database connection."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def env(name, default=None):
    v = os.environ.get(name) or default
    if v is None:
        raise SystemExit(f"{name} is not set. Add it to .env (see .env.example).")
    return v


def connect():
    import psycopg
    return psycopg.connect(env("DATABASE_URL"))
