"""Structural and plausibility checks on the seed CSVs. Run before every load.

    python validate_seed.py        # exit 1 on any error; warnings don't fail

Errors are things the database or the app would get wrong. Warnings are
things a human should look at before signing a row off.
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANIMAL = {"", "pork", "beef", "other_meat", "poultry", "fish", "shellfish",
          "dairy", "egg", "honey", "other_animal"}
SECTIONS = {"", "produce", "meat-seafood", "dairy-eggs", "bakery", "pantry",
            "spices", "frozen", "other"}
QUALITY = {"verified", "researched", "derived", "estimated"}
PORTION_SOURCES = {"USDA", "LABEL", "MEASURED", "ESTIMATE"}
BOOL = {"True", "False"}
# Meat or fish rows whose low protein is real, not a wrong record.
LOW_PROTEIN_OK = {
    "pork-belly": "about 53% fat (FDC 167812)",
    "imitation-crab": "surimi bulked with starch (FDC 174203)",
}
BOOL_COLUMNS = ["negligible_calorie", "is_divisible", "has_milk", "has_egg", "has_fish",
                "has_shellfish", "has_tree_nut", "has_peanut", "has_wheat", "has_soy",
                "has_sesame", "has_gluten", "has_alcohol", "allergens_reviewed",
                "shopping_exempt", "needs_verification"]


def read(name: str) -> list[dict]:
    with (HERE / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(value: str):
    return float(value) if value not in ("", None) else None


def check(ingredients, portions, units):
    errors, warnings = [], []
    unit_slugs = {u["slug"] for u in units}
    slugs = [i["slug"] for i in ingredients]
    if len(slugs) != len(set(slugs)):
        errors.append("duplicate ingredient slugs")

    # An alias claimed by two ingredients silently matches only one of them.
    owner = {}
    for i in ingredients:
        for term in {i["name"].lower(), *filter(None, i["aliases"].lower().split("|"))}:
            term = term.strip()
            if owner.setdefault(term, i["slug"]) != i["slug"]:
                errors.append(f"term {term!r} is on both {owner[term]} and {i['slug']}")

    for i in ingredients:
        s = i["slug"]
        for col in BOOL_COLUMNS:
            if i[col] not in BOOL:
                errors.append(f"{s}: {col} is {i[col]!r}, expected True/False")
        if i["animal_source"] not in ANIMAL:
            errors.append(f"{s}: animal_source {i['animal_source']!r}")
        if i["store_section"] not in SECTIONS:
            errors.append(f"{s}: store_section {i['store_section']!r}")
        if i["data_quality"] not in QUALITY:
            errors.append(f"{s}: data_quality {i['data_quality']!r}")
        if i["data_quality"] == "verified" and not (i["source_ref"] and i["verified_by"]):
            errors.append(f"{s}: verified without source_ref and verified_by")
        if i["animal_source"] == "dairy" and i["has_milk"] != "True":
            errors.append(f"{s}: dairy but has_milk is not set")
        if i["animal_source"] == "egg" and i["has_egg"] != "True":
            errors.append(f"{s}: egg but has_egg is not set")
        if i["animal_source"] == "fish" and i["has_fish"] != "True":
            errors.append(f"{s}: fish but has_fish is not set")
        if i["has_wheat"] == "True" and i["has_gluten"] != "True":
            errors.append(f"{s}: wheat without gluten")

        kcal, p, c, f = (num(i[k]) for k in ("kcal_100g", "protein_100g", "carb_100g", "fat_100g"))
        if kcal is None:
            errors.append(f"{s}: no kcal")
            continue
        for key in ("fiber_100g", "sugar_100g", "sodium_mg_100g"):
            if i[key] == "":
                warnings.append(f"{s}: {key} not published by USDA for this record")
        # Atwater: 4/4/9 kcal per g, with fiber at 2 kcal/g because USDA's
        # carbohydrate is "by difference" and includes it. Specific factors
        # still make real values drift, so this only catches gross errors
        # like a wrong record or a unit slip.
        if not i["macro_check_exempt"] and i["negligible_calorie"] != "True" and None not in (p, c, f):
            fiber = num(i["fiber_100g"]) or 0
            atwater = 4 * p + 4 * (c - fiber) + 2 * fiber + 9 * f
            if abs(atwater - kcal) > max(20, 0.2 * kcal):
                warnings.append(f"{s}: {kcal:g} kcal but macros give {atwater:.0f}")
        if (p is not None and i["category"] in ("meat", "poultry", "seafood") and p < 12
                and s not in LOW_PROTEIN_OK):
            errors.append(f"{s}: {p:g} g protein is not meat or fish")

    seen_default = set()
    for r in portions:
        tag = f"portion {r['slug']}/{r['unit']}/{r['modifier']!r}"
        if r["slug"] not in slugs:
            errors.append(f"{tag}: unknown ingredient")
        if r["unit"] not in unit_slugs:
            errors.append(f"{tag}: unknown unit")
        if not (num(r["grams"]) or 0) > 0:
            errors.append(f"{tag}: grams must be positive")
        if r["source"] not in PORTION_SOURCES or not r["source_ref"]:
            errors.append(f"{tag}: source {r['source']!r} needs one of {sorted(PORTION_SOURCES)} "
                          "and a source_ref")
        if r["is_default"] == "True":
            key = (r["slug"], r["unit"])
            if key in seen_default:
                errors.append(f"{tag}: second default for this unit")
            seen_default.add(key)
    return errors, warnings


def main() -> int:
    errors, warnings = check(read("ingredients_seed.csv"),
                             read("ingredient_portions_seed.csv"), read("units.csv"))
    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("ERROR:", e)
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
