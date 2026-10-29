"""Structural checks on units.csv. The parser matches aliases longest-first,
so an alias claimed by two units would silently pick one of them."""
import csv
from pathlib import Path

UNITS = Path(__file__).resolve().parents[1] / "units.csv"
KINDS = {"mass", "volume", "count", "subjective"}


def rows():
    with UNITS.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_kinds_and_factors():
    for r in rows():
        assert r["kind"] in KINDS, r["slug"]
        measured = r["kind"] in ("mass", "volume")
        assert bool(r["factor_to_base"]) == measured, (
            f"{r['slug']}: mass/volume need a factor, count/subjective must not have one")
        if measured:
            assert float(r["factor_to_base"]) > 0, r["slug"]


def test_slugs_unique():
    slugs = [r["slug"] for r in rows()]
    assert len(slugs) == len(set(slugs))


def test_no_alias_claimed_by_two_units():
    owner = {}
    for r in rows():
        for alias in filter(None, (a.strip() for a in r["aliases"].split("|"))):
            key = alias.lower()
            assert owner.setdefault(key, r["slug"]) == r["slug"], (
                f"alias {alias!r} is on both {owner[key]} and {r['slug']}")


def test_us_volume_factors():
    # US customary, not imperial or metric-rounded: a "cup" here is 236.588 ml,
    # not 240 or 250.
    f = {r["slug"]: float(r["factor_to_base"]) for r in rows() if r["factor_to_base"]}
    assert abs(f["tbsp"] - 3 * f["tsp"]) < 0.001
    assert abs(f["cup"] - 16 * f["tbsp"]) < 0.01
    assert abs(f["cup"] - 8 * f["fl-oz"]) < 0.01
    assert abs(f["lb"] - 16 * f["oz"]) < 0.01
