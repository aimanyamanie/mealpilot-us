"""USDA FoodData Central client, with a local cache.

FoodData Central is public domain (CC0), so its numbers can be stored.
Set FDC_API_KEY in .env (free key from https://fdc.nal.usda.gov/api-key-signup).
Without one, DEMO_KEY is used: 30 requests an hour, 50 a day.

    python usda.py search chicken thigh meat and skin raw
    python usda.py show 170859 173410
"""
import json
import sys
from pathlib import Path

import requests

from db import env

API = "https://api.nal.usda.gov/fdc/v1"
CACHE = Path(__file__).parent / "data" / "usda"
DATA_TYPES = ["Foundation", "SR Legacy"]


def _key():
    return env("FDC_API_KEY", "DEMO_KEY")


def search(query, data_types=DATA_TYPES, size=8):
    r = requests.get(f"{API}/foods/search", timeout=30, params={
        "api_key": _key(), "query": query, "pageSize": size,
        "dataType": ",".join(data_types)})
    r.raise_for_status()
    return r.json()["foods"]


def get_foods(fdc_ids):
    """Full records for these FDC ids, from the cache where possible."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out, missing = {}, []
    for i in map(int, fdc_ids):
        p = CACHE / f"{i}.json"
        if p.exists():
            out[i] = json.loads(p.read_text(encoding="utf-8"))
        else:
            missing.append(i)
    for start in range(0, len(missing), 20):
        batch = missing[start:start + 20]
        r = requests.post(f"{API}/foods", params={"api_key": _key()}, timeout=60,
                          json={"fdcIds": batch, "format": "full"})
        r.raise_for_status()
        for food in r.json():
            i = int(food["fdcId"])
            (CACHE / f"{i}.json").write_text(json.dumps(food), encoding="utf-8")
            out[i] = food
    lost = [i for i in map(int, fdc_ids) if i not in out]
    if lost:
        raise LookupError(f"FDC ids not found: {lost}")
    return out


def portions(food):
    """(amount, unit text, modifier, grams) for each household measure in a record."""
    rows = []
    for p in food.get("foodPortions", []):
        unit = (p.get("measureUnit") or {}).get("name") or ""
        if unit == "undetermined":
            unit = ""
        rows.append((p.get("amount") or 1, unit, p.get("modifier") or "",
                     p.get("portionDescription") or "", p["gramWeight"]))
    return rows


def nutrients(food):
    """{nutrient number: (name, unit, amount per 100 g)}."""
    out = {}
    for n in food.get("foodNutrients", []):
        meta = n.get("nutrient") or {}
        num, amt = meta.get("number"), n.get("amount")
        if num and amt is not None:
            out[num] = (meta["name"], meta["unitName"], amt)
    return out


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "search":
        for f in search(" ".join(args)):
            print(f"{f['fdcId']:>8}  {f['dataType']:<11} {f['description']}")
    elif cmd == "show":
        for i, f in get_foods(args).items():
            n = nutrients(f)
            kcal = n.get("208") or n.get("957") or n.get("958")
            print(f"\n{i}  {f['dataType']}  {f['description']}")
            print("   kcal/100g:", kcal and kcal[2], " protein:", n.get("203", ("", "", None))[2],
                  " fat:", n.get("204", ("", "", None))[2], " carb:", n.get("205", ("", "", None))[2],
                  " sodium mg:", n.get("307", ("", "", None))[2])
            for row in portions(f):
                print("   portion:", row)
