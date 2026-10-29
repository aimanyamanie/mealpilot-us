"""Guardrails for YouTube-derived test data (CLAUDE.md, Recipe sourcing,
test-only exception).

Everything built from YouTube Data API responses goes to the Neon branch
dev-youtube-test and nowhere else. connect() refuses any other database,
including main, even if someone edits .env.test by mistake.
"""
import os
from pathlib import Path

import psycopg
from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data" / "youtube"          # gitignored with pipeline/data/
TEST_BRANCH = "dev-youtube-test"
RETENTION_DAYS = 30


def test_database_url() -> str:
    test = dotenv_values(ROOT / ".env.test")
    main = dotenv_values(ROOT / ".env")
    url = test.get("DATABASE_URL")
    if not url:
        raise SystemExit(".env.test has no DATABASE_URL: run `neon connection-string "
                         f"{TEST_BRANCH} --pooled` and write it there.")
    if test.get("NEON_BRANCH") != TEST_BRANCH:
        raise SystemExit(f".env.test must say NEON_BRANCH={TEST_BRANCH}.")
    if url == main.get("DATABASE_URL") or url == main.get("DATABASE_URL_UNPOOLED"):
        raise SystemExit(".env.test points at the same database as .env (main). Refusing.")
    return url


def connect() -> psycopg.Connection:
    conn = psycopg.connect(test_database_url())
    # Belt and braces: the endpoint itself must not be main's.
    main_url = dotenv_values(ROOT / ".env").get("DATABASE_URL") or ""
    host = conn.info.host
    if host and host in main_url:
        conn.close()
        raise SystemExit("Connected host is main's endpoint. Refusing.")
    return conn


def api_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY") or dotenv_values(ROOT / ".env").get("YOUTUBE_API_KEY")
    if not key:
        raise SystemExit("YOUTUBE_API_KEY is empty in .env. Create one in Google Cloud "
                         "(YouTube Data API v3) and paste it there.")
    return key
