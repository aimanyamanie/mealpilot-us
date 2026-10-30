"""The creator permissions register: who agreed to what, and the evidence.

permissions.csv (committed) has one row per creator:
  status       none | requested | granted | declined
  date         when the status last changed (YYYY-MM-DD)
  channel_used where it was agreed: Instagram DM, email, signed agreement
  scope        what they agreed to, pipe-separated, from SCOPES
  evidence     screenshot or document file name in permissions/evidence/
               (gitignored: private conversations stay off git)
  obtained_by  who got it

    python permissions.py          # check the register, sync status to main

Only 'granted' with 'recipe_data' in scope lets load_cards.py or
fetch_card.py read a creator's recipes. Changing a row to 'declined'
and re-syncing removes their recipes from v_published_recipes.
"""
import csv
import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
REGISTER = HERE / "permissions.csv"
EVIDENCE = HERE.parent / "permissions" / "evidence"
STATUSES = {"none", "requested", "granted", "declined"}
SCOPES = {"recipe_data", "name", "thumbnail", "embed", "promo_code", "revenue_share"}


def read() -> dict:
    with REGISTER.open(encoding="utf-8", newline="") as f:
        return {r["slug"]: r for r in csv.DictReader(f)}


def problems(rows: dict) -> list[str]:
    out = []
    for slug, r in rows.items():
        if r["status"] not in STATUSES:
            out.append(f"{slug}: status {r['status']!r}")
        scope = set(filter(None, r["scope"].split("|")))
        if scope - SCOPES:
            out.append(f"{slug}: unknown scope {sorted(scope - SCOPES)}")
        if r["status"] == "granted":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]):
                out.append(f"{slug}: granted needs a date")
            if "recipe_data" not in scope:
                out.append(f"{slug}: granted without recipe_data in scope")
            if not r["evidence"]:
                out.append(f"{slug}: granted needs an evidence file")
            elif not (EVIDENCE / r["evidence"]).exists():
                out.append(f"{slug}: evidence file {r['evidence']} not found in permissions/evidence/")
            if not r["obtained_by"]:
                out.append(f"{slug}: granted needs obtained_by")
    return out


def granted(slug: str) -> dict:
    """The register row if this creator granted recipe data, else exit."""
    rows = read()
    row = rows.get(slug)
    issues = [p for p in problems(rows) if p.startswith(f"{slug}:")]
    if not row or row["status"] != "granted" or issues:
        raise SystemExit(f"{slug}: no usable permission in permissions.csv "
                         f"({row['status'] if row else 'not listed'}{'; ' + '; '.join(issues) if issues else ''}).")
    return row


def sync(conn, rows: dict) -> int:
    n = 0
    for slug, r in rows.items():
        n += conn.execute(
            "UPDATE creators SET permission_status = %s, permission_ref = %s, updated_at = now() "
            "WHERE slug = %s AND (permission_status <> %s OR permission_ref IS DISTINCT FROM %s)",
            [r["status"], r["evidence"] or None, slug, r["status"], r["evidence"] or None]).rowcount
    return n


def main() -> int:
    rows = read()
    issues = problems(rows)
    for p in issues:
        print("PROBLEM:", p)
    if issues:
        return 1
    load_dotenv(HERE.parent / ".env")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        print(f"{len(rows)} creators in the register; {sync(conn, rows)} changed on main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
