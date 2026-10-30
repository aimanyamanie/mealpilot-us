"""Build ingredients_seed.csv and ingredient_portions_seed.csv from
ingredient_list.csv (what each ingredient is) and usda_picks.csv (which
USDA record it was matched to, chosen by reading the description).

    python usda.py index        # once, after downloading the USDA JSON
    python build_seed.py

Nutrition comes from the picked record. Portions (cup, tbsp, "1 medium",
"1 clove") come from the portion records, usually the SR Legacy twin,
because Foundation Foods publishes few household measures. Weights neither
record has (a cup of Greek yogurt, one shallot) go in extra_portions.csv
with their source: USDA's survey database (FNDDS), a product label from
USDA Branded Foods, or a measurement.

Allergens and diet come from ingredient_list.csv. A row is only signed off
(needs_verification = false, allergens_reviewed = true, a portion's
reviewed_by) where signoffs.csv / portion_signoffs.csv approve exactly what
is being built: the same FDC id, the same flags, the same grams. Those
files are written by apply_review.py from the review workbook.
"""
import csv
import re
from datetime import date
from pathlib import Path

from make_review_sheet import allergen_summary
from usda import load_index

HERE = Path(__file__).resolve().parent
TODAY = date.today().isoformat()
CUP_ML, TBSP_ML, TSP_ML = 236.588, 14.7868, 4.92892

ALLERGEN_COLUMNS = {
    "milk": "has_milk", "egg": "has_egg", "fish": "has_fish",
    "shellfish": "has_shellfish", "tree_nut": "has_tree_nut",
    "peanut": "has_peanut", "wheat": "has_wheat", "soy": "has_soy",
    "sesame": "has_sesame", "gluten": "has_gluten", "alcohol": "has_alcohol",
}
# Rows whose calories are real but negligible, and rows that are never bought.
NEGLIGIBLE = {"water", "salt", "baking-soda"}
SHOPPING_EXEMPT = {"water": "tap water"}
# Energy outside protein/carb/fat, or carbohydrate that is not metabolised.
MACRO_EXEMPT = {
    "wine-white": "alcohol", "wine-red": "alcohol", "vanilla-extract": "alcohol",
    "vodka": "alcohol",
    "baking-powder": "leavening salts, not metabolised",
    "baking-soda": "sodium bicarbonate, no energy",
}
# Picks that stand in for a food USDA does not publish.
PROXIES = {"mustard-dijon", "vinegar-rice", "chocolate-chips", "breadcrumbs-panko",
           "tapioca-starch"}

UNIT_WORDS = {
    "cup": "cup", "cups": "cup",
    "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "clove": "clove", "cloves": "clove",
    "slice": "slice", "slices": "slice",
    "stalk": "stalk", "stalks": "stalk",
    "leaf": "leaf", "leaves": "leaf",
    "sprig": "sprig", "sprigs": "sprig",
    "head": "head", "bunch": "bunch",
    "stick": "stick", "sticks": "stick",
    "fillet": "fillet", "piece": "piece", "pieces": "piece", "each": "piece",
    "can": "can",
}
SIZE_WORDS = {"extra", "large", "medium", "small", "jumbo"}
FILLER = {"of", "or", "and", "a", "1"}
# Qualifiers that mean the ordinary form a recipe means by the bare measure.
PLAIN = {"fluid", "leaves", "shelled", "unsifted", "raw", "whole", "packet", "edible",
         "solid", "kernels", "halves"}
NORMALISE = {"cubes": "cubed", "slices": "sliced", "strips": "sliced", "chunks": "chunks"}
EXCLUDE = ["crust not eaten", "with hulls", "in shell", "individual packet",
           "with refuse", "bone and skin", "prepared"]
ODD_PIECE = {"plum", "italian", "cherry", "wedge", "slice", "peeled", "unpeeled",
             "miniature", "tip", "serving", "packet", "box"}
# Which measure a recipe means when it gives no qualifier, where USDA has no
# unqualified measure: "1 cup brown sugar" is packed; a cup of dry pasta is
# taken as penne (the middle of USDA's shapes, 64-122 g).
DEFAULT_MODIFIER = {("brown-sugar", "cup"): "packed", ("brown-sugar", "tbsp"): "packed",
                    ("pasta-dry", "cup"): "penne", ("pasta-whole-wheat-dry", "cup"): "penne"}
SIZES = ["extra large", "jumbo", "large", "medium", "small"]
DEFAULT_SIZE = {"egg": "large"}
PREP = ["chopped", "sliced", "diced", "minced", "shredded", "grated", "packed",
        "cubed", "mashed", "crumbled", "slivered", "ground", "halves", "whole",
        "florets", "pieces", "melted", "pureed"]
# Measures that are not household units, or are already covered by mass units.
SKIP_WORDS = {"oz", "lb", "g", "racc", "serving", "nlea", "package", "container",
              "rings", "cubic", "fl", "quart", "pint", "bar"}


def map_portion(p: dict):
    """USDA portion -> (unit slug, modifier, grams for ONE unit), or None.

    A qualifier USDA gives is KEPT as the modifier, never dropped: dropping
    it once made "cup, whipped" (120 g) the plain cup of heavy cream, and
    "cup, in shell" the plain cup of walnuts. Only words that mean the
    ordinary form (PLAIN) collapse to ''. Measures of an inedible or
    non-household form (EXCLUDE) are skipped."""
    if not p.get("grams") or not p.get("amount"):
        return None
    raw = f"{p['unit']} {p['modifier']}".lower()
    if any(phrase in raw for phrase in EXCLUDE):
        return None
    paren = " ".join(re.findall(r"\(([^)]*)\)", raw))
    text = re.sub(r"\([^)]*\)", " ", raw).replace(",", " ")
    words = text.split()
    if not words:
        return None
    grams = p["grams"] / p["amount"]
    # "fl oz" is the only household measure USDA gives for many liquids
    # (wine, water, juice): without it they have no density at all.
    if words[:2] == ["fl", "oz"] and len(words) == 2:
        return "fl-oz", "", grams
    if words[0] in SKIP_WORDS:
        return None
    size = next((s for s in SIZES if re.search(rf"\b{s}\b", text)), "")
    rest = [w for w in words[1:] if w not in SIZE_WORDS and w not in FILLER and not w.isdigit()]
    if words[0] in UNIT_WORDS:
        unit = UNIT_WORDS[words[0]]
        if unit in ("cup", "tbsp", "tsp"):
            prep = next((w for w in PREP if w in rest), None)
            if prep:
                return unit, prep, grams
            rest = [NORMALISE.get(w, w) for w in rest if w not in PLAIN]
            return unit, " ".join(rest), grams
        if unit == "can":
            # "can (12.5 oz), drained": the size is the modifier, so a 12.5 oz
            # can never becomes the default can.
            size_text = re.search(r"[\d.]+\s*(?:oz|g|lb)", paren)
            return unit, size_text.group(0) if size_text else "", grams
        rest = [w for w in rest if w not in PLAIN]
        return unit, size or " ".join(rest), grams
    if words[0] in SIZES or words[0] == "extra":
        return "piece", size, grams
    # The measure names the food itself ("1 almond", "1 thigh without skin",
    # Foundation's "1 Onion, Edible"): one whole piece, unless it is an
    # unusual form ("plum tomato", "wedge", "eggplant, peeled").
    if p["amount"] == 1:
        odd = [w for w in words if w in ODD_PIECE]
        if odd:
            return "piece", " ".join(words), grams
        return "piece", size, grams
    return None


def portions_for(slug: str, fdc_ids: list[int], foods: dict, extras=()) -> list[dict]:
    rows, seen = [], set()
    for fdc_id in fdc_ids:
        food = foods[fdc_id]
        for p in food["portions"]:
            mapped = map_portion(p)
            if not mapped:
                continue
            unit, modifier, grams = mapped
            if (unit, modifier) in seen:
                continue                      # first record listed wins
            seen.add((unit, modifier))
            label = " ".join(filter(None, [str(p["amount"]), p["unit"], p["modifier"]]))
            rows.append({"slug": slug, "unit": unit, "modifier": modifier,
                         "grams": round(grams, 3), "source": "USDA",
                         "source_ref": f"FDC {fdc_id}: {label}", "is_default": False,
                         "reviewed_by": "", "reviewed_at": ""})
    # Weights the picked records lack, from extra_portions.csv: another USDA
    # dataset (FNDDS), a product label, or a measurement, each with its source.
    for e in extras:
        if (e["unit"], e["modifier"]) in seen:
            raise SystemExit(f"{slug}: extra portion 1 {e['unit']} {e['modifier']} "
                             "duplicates a USDA portion; remove it from extra_portions.csv")
        seen.add((e["unit"], e["modifier"]))
        rows.append({"slug": slug, "unit": e["unit"], "modifier": e["modifier"],
                     "grams": round(float(e["grams"]), 3), "source": e["source"],
                     "source_ref": e["source_ref"], "is_default": False,
                     "reviewed_by": "", "reviewed_at": ""})
    # One default per unit: the unqualified measure, else the usual size
    # (medium; large for eggs, which US recipes assume), else the first.
    usual = DEFAULT_SIZE.get(slug, "medium")
    for unit in {r["unit"] for r in rows}:
        group = [r for r in rows if r["unit"] == unit]
        override = DEFAULT_MODIFIER.get((slug, unit))
        pick = (next((r for r in group if override and r["modifier"] == override), None)
                or next((r for r in group if r["modifier"] == ""), None)
                or next((r for r in group if r["modifier"] == usual), None))
        if pick is None and unit not in ("can",):
            pick = group[0]
        if pick:
            pick["is_default"] = True
    return rows


def density(portions: list[dict]):
    """g/ml from an unqualified cup, fl oz, tbsp or tsp, in that order of preference."""
    for unit, ml in (("cup", CUP_ML), ("fl-oz", 29.5735), ("tbsp", TBSP_ML), ("tsp", TSP_ML)):
        for r in portions:
            if r["unit"] == unit and r["modifier"] == "":
                return round(r["grams"] / ml, 3)
    return None


def main() -> None:
    foods = load_index()
    with (HERE / "ingredient_list.csv").open(encoding="utf-8", newline="") as f:
        items = list(csv.DictReader(f))
    with (HERE / "usda_picks.csv").open(encoding="utf-8", newline="") as f:
        picks = {r["slug"]: r for r in csv.DictReader(f)}
    missing = [i["slug"] for i in items if i["slug"] not in picks]
    if missing:
        raise SystemExit(f"no USDA pick for: {', '.join(missing)}")
    extras = {}
    with (HERE / "extra_portions.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            extras.setdefault(r["slug"], []).append(r)
    unknown = set(extras) - {i["slug"] for i in items}
    if unknown:
        raise SystemExit(f"extra_portions.csv: unknown ingredient {', '.join(sorted(unknown))}")
    signoffs = read_optional("signoffs.csv", lambda r: r["slug"])
    portion_signoffs = read_optional("portion_signoffs.csv",
                                     lambda r: (r["slug"], r["unit"], r["modifier"]))
    stale = []

    seed, all_portions = [], []
    for item in items:
        slug, pick = item["slug"], picks[item["slug"]]
        food = foods[int(pick["fdc_id"])]
        v = dict(food["per_100g"])
        portion_ids = [int(x) for x in pick["portion_fdc_ids"].split("|") if x]
        # Foundation records often omit fiber or sugar (meat, fish, dairy). The
        # SR Legacy twin picked for portions describes the same food, so a
        # missing value is taken from it, and the note says which nutrient.
        borrowed = []
        for twin_id in (i for i in portion_ids if i != food["fdc_id"]):
            twin = foods[twin_id]["per_100g"]
            for key in ("fiber", "sugar", "sodium_mg"):
                if v[key] is None and twin[key] is not None:
                    v[key] = twin[key]
                    borrowed.append(f"{key} from FDC {twin_id}")
        portions = portions_for(slug, portion_ids, foods, extras.get(slug, []))
        all_portions += portions
        allergens = set(filter(None, item["allergens"].split("|")))
        unknown = allergens - set(ALLERGEN_COLUMNS)
        if unknown:
            raise SystemExit(f"{slug}: unknown allergen code {unknown}")
        proxy = slug in PROXIES
        notes = [f"energy from FDC nutrient {food['energy_nutrient']}"]
        if pick["pick_note"]:
            notes.append(pick["pick_note"])
        notes += borrowed
        if len(set(portion_ids) - {food["fdc_id"]}):
            notes.append(f"portions from FDC {pick['portion_fdc_ids']}")
        notes.append("record chosen by Claude from its description on "
                     f"{TODAY}; awaiting human sign-off")
        row = {
            "slug": slug, "name": item["name"], "aliases": item["aliases"],
            "category": item["category"],
            "kcal_100g": v["kcal"], "protein_100g": v["protein"],
            "carb_100g": v["carb"], "fat_100g": v["fat"],
            "fiber_100g": v["fiber"], "sugar_100g": v["sugar"],
            "sodium_mg_100g": v["sodium_mg"],
            "negligible_calorie": slug in NEGLIGIBLE,
            "macro_check_exempt": MACRO_EXEMPT.get(slug, ""),
            "density_g_per_ml": density(portions) or "",
            "edible_pct": 100,
            "is_divisible": item["divisible"].strip().lower() != "false",
            **{col: code in allergens for code, col in ALLERGEN_COLUMNS.items()},
            "animal_source": item["animal_source"],
            "allergens_reviewed": False,
            "allergens_note": item["note"],
            "store_section": item["store_section"],
            "shopping_exempt": slug in SHOPPING_EXEMPT,
            "shopping_exempt_reason": SHOPPING_EXEMPT.get(slug, ""),
            "nutrition_source": "USDA",
            "source_ref": f"FDC {food['fdc_id']}",
            "source_version": food["version"],
            "source_description": food["description"],
            "data_quality": "researched" if proxy else "verified",
            "needs_verification": True,
            "verified_by": "" if proxy else "claude (description read)",
            "verified_at": "",
            "notes": "; ".join(notes),
        }
        stale += apply_signoff(row, signoffs.get(slug), food["fdc_id"])
        for p in portions:
            stale += apply_portion_signoff(p, portion_signoffs.get(
                (p["slug"], p["unit"], p["modifier"])))
        seed.append(row)

    write(HERE / "ingredients_seed.csv", seed)
    write(HERE / "ingredient_portions_seed.csv", all_portions)
    for s in stale:
        print("sign-off no longer applies:", s)
    signed = sum(1 for r in seed if not r["needs_verification"])
    reviewed = sum(1 for r in seed if r["allergens_reviewed"])
    print(f"{len(seed)} ingredients ({signed} nutrition signed off, {reviewed} allergens "
          f"reviewed), {len(all_portions)} portions "
          f"({sum(1 for p in all_portions if p['reviewed_by'])} reviewed)")


def read_optional(name: str, key) -> dict:
    path = HERE / name
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {key(r): r for r in csv.DictReader(f)}


def apply_signoff(row: dict, signoff, fdc_id: int) -> list[str]:
    """Mark a row signed off where the reviewer approved exactly this record
    and these flags. Returns why an earlier approval no longer applies."""
    if not signoff:
        return []
    stale = []
    if signoff["nutrition"] == "Approve":
        if signoff["fdc_id"] == str(fdc_id):
            row["needs_verification"] = False
            row["verified_by"] = signoff["reviewer"]
            row["verified_at"] = signoff["reviewed_on"]
        else:
            stale.append(f"{row['slug']}: nutrition approved for FDC {signoff['fdc_id']}, "
                         f"now FDC {fdc_id}")
    if signoff["allergens"] == "Approve" and signoff["diet"] == "Approve":
        if signoff["flags_snapshot"] == allergen_summary(row):
            row["allergens_reviewed"] = True
        else:
            stale.append(f"{row['slug']}: flags approved as '{signoff['flags_snapshot']}', "
                         f"now '{allergen_summary(row)}'")
    return stale


def apply_portion_signoff(portion: dict, signoff) -> list[str]:
    if not signoff or signoff["status"] != "Approve":
        return []
    if signoff["grams"] != f"{portion['grams']:g}":
        return [f"{portion['slug']} 1 {portion['unit']} {portion['modifier']}: approved at "
                f"{signoff['grams']} g, now {portion['grams']:g} g"]
    portion["reviewed_by"] = signoff["reviewer"]
    portion["reviewed_at"] = signoff["reviewed_on"]
    return []


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})


if __name__ == "__main__":
    main()
