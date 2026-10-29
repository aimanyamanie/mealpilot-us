"""Load units.csv, ingredients_seed.csv and ingredient_portions_seed.csv
into Postgres. The CSVs are the source of truth; the app never writes these
tables.

    python validate_seed.py && python load_seed.py

Units and ingredients are upserted by slug, so ids stay stable for recipes
that already reference them. Portions are replaced per ingredient.
Never adds columns: a CSV column the table lacks is an error, fixed in
schema.sql.
"""
import csv
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from validate_seed import check, read

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / ".env")


def value(v: str):
    if v == "":
        return None
    if v in ("True", "False"):
        return v == "True"
    return v


def upsert(conn, table: str, rows: list[dict]) -> int:
    cols = list(rows[0])
    table_cols = {r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s", [table])}
    extra = set(cols) - table_cols
    if extra:
        sys.exit(f"{table}: CSV columns not in schema.sql: {sorted(extra)}")
    names = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "slug")
    touch = ", updated_at = now()" if "updated_at" in table_cols else ""
    sql = (f"INSERT INTO {table} ({names}) VALUES ({marks}) "
           f"ON CONFLICT (slug) DO UPDATE SET {updates}{touch}")
    with conn.cursor() as cur:
        cur.executemany(sql, [[value(r[c]) for c in cols] for r in rows])
    return len(rows)


def load_portions(conn, rows: list[dict]) -> int:
    ids = dict(conn.execute("SELECT slug, id FROM ingredients").fetchall())
    units = dict(conn.execute("SELECT slug, id FROM units").fetchall())
    slugs = sorted({r["slug"] for r in rows})
    with conn.cursor() as cur:
        cur.execute("DELETE FROM ingredient_portions WHERE ingredient_id = ANY(%s)",
                    [[ids[s] for s in slugs]])
        cur.executemany(
            "INSERT INTO ingredient_portions (ingredient_id, unit_id, modifier, grams, "
            "source, source_ref, is_default) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [[ids[r["slug"]], units[r["unit"]], r["modifier"], r["grams"], r["source"],
              r["source_ref"], r["is_default"] == "True"] for r in rows])
    return len(rows)


def main() -> None:
    units, ingredients = read("units.csv"), read("ingredients_seed.csv")
    portions = read("ingredient_portions_seed.csv")
    errors, _ = check(ingredients, portions, units)
    if errors:
        sys.exit(f"{len(errors)} validation errors: run validate_seed.py")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.transaction():
            print("units", upsert(conn, "units", units))
            print("ingredients", upsert(conn, "ingredients", ingredients))
            print("portions", load_portions(conn, portions))


if __name__ == "__main__":
    main()
