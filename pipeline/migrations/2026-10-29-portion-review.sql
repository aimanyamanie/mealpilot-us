-- Adds the human sign-off of a portion weight. schema.sql already has these
-- columns; this brings a database created before 2026-10-29 up to date.
-- Safe to re-run.  python apply_sql.py migrations/2026-10-29-portion-review.sql
ALTER TABLE ingredient_portions ADD COLUMN IF NOT EXISTS reviewed_by text;
ALTER TABLE ingredient_portions ADD COLUMN IF NOT EXISTS reviewed_at date;
