"""USDA FoodData Central: a compact local index and a search helper.

Reads the bulk JSON downloads in data/usda/ (Foundation Foods + SR Legacy,
public domain) so the seed can be built without an API key.

    python usda.py index                    # build data/usda/index.json once
    python usda.py search chicken thigh     # rank candidates for an ingredient
    python usda.py show 2646170             # one record: nutrients and portions

Search only proposes candidates. Choosing the record is the dangerous step:
read the description against what the ingredient means, then check the
macros fit the food. Never pick the top hit unread.
"""
import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "usda"
INDEX = DATA / "index.json"
SOURCES = {
    "foundation": ("FoodData_Central_foundation_food_json_2026-10-29.json",
                   "FoundationFoods", "FDC Foundation 2026-10"),
    "sr_legacy": ("FoodData_Central_sr_legacy_food_json_2018-04.json",
                  "SRLegacyFoods", "FDC SR Legacy 2018-04"),
}

# FDC nutrient numbers, in order of preference where there is more than one.
# Foundation Foods often has no 208 (Energy) and reports Atwater energy instead.
NUTRIENTS = {
    "kcal": ["208", "958", "957"],
    "protein": ["203"],
    "fat": ["204"],
    "carb": ["205", "205.2"],
    "fiber": ["291"],
    "sugar": ["269", "269.3"],
    "sodium_mg": ["307"],
    "alcohol": ["221"],
}


def _pick(nutrients: dict, numbers: list[str]):
    for num in numbers:
        if num in nutrients:
            return nutrients[num], num
    return None, None


def _compact(food: dict, dataset: str) -> dict:
    by_number = {}
    for n in food.get("foodNutrients", []):
        num = n.get("nutrient", {}).get("number")
        if num and n.get("amount") is not None:
            by_number[num] = n["amount"]
    values, used = {}, {}
    for key, numbers in NUTRIENTS.items():
        values[key], used[key] = _pick(by_number, numbers)
    portions = []
    for p in food.get("foodPortions", []):
        unit = (p.get("measureUnit") or {}).get("name", "")
        portions.append({
            "amount": p.get("amount") or p.get("value"),
            "unit": "" if unit == "undetermined" else unit,
            "modifier": (p.get("modifier") or "").strip(),
            "description": (p.get("portionDescription") or "").strip(),
            "grams": p.get("gramWeight"),
        })
    return {
        "fdc_id": food["fdcId"],
        "dataset": dataset,
        "version": SOURCES[dataset][2],
        "description": food["description"],
        "category": (food.get("foodCategory") or {}).get("description", ""),
        "per_100g": values,
        "energy_nutrient": used["kcal"],
        "portions": portions,
    }


def build_index() -> None:
    foods = []
    for dataset, (filename, key, _) in SOURCES.items():
        with (DATA / filename).open(encoding="utf-8") as f:
            for food in json.load(f)[key]:
                foods.append(_compact(food, dataset))
    INDEX.write_text(json.dumps(foods), encoding="utf-8")
    print(f"indexed {len(foods)} foods -> {INDEX.name}")


def load_index() -> dict[int, dict]:
    if not INDEX.exists():
        sys.exit("No index yet: run `python usda.py index` first.")
    return {f["fdc_id"]: f for f in json.loads(INDEX.read_text(encoding="utf-8"))}


def search(foods: dict[int, dict], query: str, limit: int = 12) -> list[dict]:
    """Rank by query words found in the description. Words at the start of the
    description (the food itself, before the qualifiers) count double, and
    Foundation Foods beat SR Legacy on ties because they are newer analyses."""
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 1]
    ranked = []
    for food in foods.values():
        desc = food["description"].lower()
        head = desc.split(",")[0]
        hits = [w for w in words if re.search(rf"\b{w}", desc)]
        if len(hits) < len(words):
            continue
        score = len(hits) + sum(1 for w in words if re.search(rf"\b{w}", head))
        score += 0.5 if food["dataset"] == "foundation" else 0
        score -= desc.count(",") * 0.1          # prefer plainer records
        ranked.append((score, food))
    ranked.sort(key=lambda t: -t[0])
    return [f for _, f in ranked[:limit]]


def fmt(food: dict) -> str:
    v = food["per_100g"]
    def n(key):
        return "-" if v[key] is None else f"{v[key]:g}"
    return (f"{food['fdc_id']:>8} {food['dataset'][:4]}  {n('kcal'):>5} kcal  "
            f"P{n('protein')} C{n('carb')} F{n('fat')}  {food['description']}")


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == "index":
        build_index()
    elif cmd == "search":
        for food in search(load_index(), " ".join(rest)):
            print(fmt(food))
    elif cmd == "candidates":
        # Top candidates for every row of ingredient_list.csv, for a human
        # (or a reviewing agent) to choose from. It proposes; it never picks.
        import csv
        foods = load_index()
        path = Path(__file__).resolve().parent / "ingredient_list.csv"
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                print(f"## {row['slug']}  [{row['query']}]")
                hits = search(foods, row["query"], limit=4)
                for food in hits:
                    print("  " + fmt(food))
                if not hits:
                    print("  (no match)")
    elif cmd == "show":
        food = load_index()[int(rest[0])]
        print(json.dumps(food, indent=2))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
