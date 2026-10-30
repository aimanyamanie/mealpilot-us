"""Shared recipe maths and writes: grams per line, nutrition per serving,
coverage, and saving a recipe with its lines, steps and nutrition.

Used by load_recipes.py (YouTube test data) and load_cards.py (licensed
recipe cards), so both apply exactly the same rules.

Grams per line, in the order CLAUDE.md sets: a mass unit; a weight the
creator states ("1/2 cup (45g)"); a stated package size ("1 (15 oz) can");
the exact ingredient_portions row; that unit's default portion; density
for a volume unit. Otherwise NULL, and the line counts against coverage.

A range ("2-3 cloves") uses the lower bound. A nutrient the ingredient
table lacks (USDA publishes no sugar for shrimp) is ignored when those
lines are under 1% of the recipe's grams; otherwise that per-serving value
is NULL and the recipe is held.
"""
import re
from decimal import Decimal
from fractions import Fraction

COVERAGE_MIN = Fraction(9, 10)
NUTRIENTS = ["kcal", "protein", "carb", "fat", "fiber", "sugar", "sodium_mg"]
NEGLIGIBLE_SHARE = Fraction(1, 100)
REFERENCE_VERSION = "FDC Foundation 2026-10 + SR Legacy 2018-04"


def frac(v):
    return None if v is None else Fraction(str(v))


def dec(v):
    if isinstance(v, Fraction):
        return Decimal(v.numerator) / Decimal(v.denominator)
    return v


def rounded(v, places):
    return None if v is None else round(dec(v), places)


def load_reference(conn):
    units = {s: (i, k, frac(f)) for i, s, k, f in
             conn.execute("SELECT id, slug, kind::text, factor_to_base FROM units")}
    ingredients = {}
    for row in conn.execute(
            "SELECT id, slug, kcal_100g, protein_100g, carb_100g, fat_100g, fiber_100g, "
            "sugar_100g, sodium_mg_100g, density_g_per_ml, edible_pct, needs_verification "
            "FROM ingredients"):
        ingredients[row[1]] = {"id": row[0], **dict(zip(NUTRIENTS, map(frac, row[2:9]))),
                               "density": frac(row[9]), "edible_pct": frac(row[10]),
                               "unverified": row[11]}
    portions, defaults = {}, {}
    for slug, unit, modifier, grams, is_default in conn.execute(
            "SELECT i.slug, u.slug, p.modifier, p.grams, p.is_default FROM ingredient_portions p "
            "JOIN ingredients i ON i.id = p.ingredient_id JOIN units u ON u.id = p.unit_id"):
        portions[(slug, unit, modifier)] = frac(grams)
        if is_default:
            defaults[(slug, unit)] = frac(grams)
    return units, ingredients, portions, defaults


def grams_for(line, ref):
    """(grams as purchased, method) or (None, reason)."""
    units, ingredients, portions, defaults = ref
    q = line["quantity"]
    if q is None:
        return None, None
    unit = line["unit"] or "piece"
    kind = units[unit][1]
    if kind == "subjective":
        return None, None
    if kind == "mass":
        return q * units[unit][2], "mass"
    if line.get("stated_grams") is not None:
        return line["stated_grams"], "mass"      # "1/2 cup (45g)": the creator's own weight
    slug = line["ingredient"]
    # "2 (15 oz) cans chickpeas, drained": the 15 oz is the can's net weight
    # WITH the liquid. Drained, a can holds about 60% of that, and the
    # nutrition record is for the drained food, so use the drained can weight.
    drained = re.search(r"\bdrain", line.get("preparation_note") or "", re.I)
    if line["package_grams"] is not None and drained and slug and (slug, "can") in defaults:
        return q * defaults[(slug, "can")], "portion"
    if line["package_grams"] is not None:
        return q * line["package_grams"], "mass"
    if slug is None:
        return None, "unmatched_ingredient"
    ing = ingredients[slug]
    if line["package_ml"] is not None and ing["density"]:
        return q * line["package_ml"] * ing["density"], "density"
    exact = portions.get((slug, unit, line["modifier"]))
    if exact:
        return q * exact, "portion"
    default = defaults.get((slug, unit))
    if default:
        return q * default, "portion"
    if kind == "volume" and ing["density"]:
        return q * units[unit][2] * ing["density"], "density"
    return None, "no_grams"


def prepare_lines(parsed_lines, ref):
    """Adds grams, method and review reason to each parsed line."""
    units, ingredients, _, _ = ref
    out = []
    for order, line in enumerate(parsed_lines):
        grams, how = grams_for(line, ref)
        kind = units[line["unit"] or "piece"][1]
        line["counts_for_coverage"] = line["quantity"] is not None and kind != "subjective"
        line["grams_as_purchased"] = grams
        edible = ingredients[line["ingredient"]]["edible_pct"] if line["ingredient"] else Fraction(100)
        line["grams_edible"] = grams * edible / 100 if grams is not None else None
        line["grams_method"] = how if grams is not None else None
        line["review_reason"] = None if grams is not None or not line["counts_for_coverage"] else how
        if line["ingredient"] is None:
            line["review_reason"] = "unmatched_ingredient"
        line["display_order"] = order
        out.append(line)
    return out


def nutrition(lines, ingredients, servings):
    computed = [l for l in lines if l["grams_edible"] is not None and l["ingredient"]]
    stated = [l for l in lines if l["counts_for_coverage"]]
    total_grams = sum((l["grams_edible"] for l in computed), Fraction(0))
    per_serving, held = {}, []
    for n in NUTRIENTS:
        missing = [l for l in computed if ingredients[l["ingredient"]][n] is None]
        missing_grams = sum((l["grams_edible"] for l in missing), Fraction(0))
        if total_grams and missing_grams / total_grams >= NEGLIGIBLE_SHARE:
            per_serving[n] = None
            held.append(f"no_{n}")
            continue
        total = sum((l["grams_edible"] * ingredients[l["ingredient"]][n] / 100
                     for l in computed if ingredients[l["ingredient"]][n] is not None), Fraction(0))
        per_serving[n] = total / servings
    coverage = (Fraction(len([l for l in stated if l["grams_edible"] is not None]), len(stated))
                if stated else Fraction(0))
    unverified = (sum((l["grams_edible"] for l in computed if ingredients[l["ingredient"]]["unverified"]),
                      Fraction(0)) / total_grams) if total_grams else None
    total_kcal = per_serving["kcal"] * servings if per_serving["kcal"] is not None else None
    return {"per_serving": per_serving, "coverage": coverage, "unverified": unverified,
            "total_kcal": total_kcal, "held": held}


def save_recipe(conn, fields: dict, lines, ref, result, steps=None) -> int:
    """Upsert the recipe by slug, then replace its lines, steps and nutrition."""
    units, ingredients, _, _ = ref
    cols = list(fields)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "slug")
    recipe_id = conn.execute(
        f"INSERT INTO recipes ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
        f"ON CONFLICT (slug) DO UPDATE SET {updates}, updated_at = now() RETURNING id",
        [fields[c] for c in cols]).fetchone()[0]
    conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = %s", [recipe_id])
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO recipe_ingredients (recipe_id, display_order, raw_text, group_label, quantity, "
            "quantity_max, unit_id, modifier, ingredient_id, preparation_note, is_optional, is_scalable, "
            "grams_as_purchased, grams_edible, grams_method, needs_review, review_reason) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [[recipe_id, l["display_order"], l["raw_text"], l.get("group_label"), dec(l["quantity"]),
              dec(l["quantity_max"]), units[l["unit"]][0] if l["unit"] else None, l["modifier"],
              ingredients[l["ingredient"]]["id"] if l["ingredient"] else None, l["preparation_note"],
              l["is_optional"], l["is_scalable"], rounded(l["grams_as_purchased"], 2),
              rounded(l["grams_edible"], 2), l["grams_method"], l["review_reason"] is not None,
              l["review_reason"]] for l in lines])
    if steps is not None:
        conn.execute("DELETE FROM steps WHERE recipe_id = %s", [recipe_id])
        with conn.cursor() as cur:
            # source_text keeps what a step will be rewritten from. It is never
            # displayed, and needs_rewrite stays true until our own wording exists.
            cur.executemany(
                "INSERT INTO steps (recipe_id, step_number, instruction, source_text, needs_rewrite) "
                "VALUES (%s, %s, '', %s, true)",
                [[recipe_id, i + 1, text] for i, text in enumerate(steps)])
    ps = result["per_serving"]
    conn.execute(
        "INSERT INTO recipe_nutrition (recipe_id, per_serving_kcal, per_serving_protein, per_serving_carb, "
        "per_serving_fat, per_serving_fiber, per_serving_sugar, per_serving_sodium_mg, total_kcal, "
        "coverage_ratio, unverified_share, reference_version, computed_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now()) "
        "ON CONFLICT (recipe_id) DO UPDATE SET per_serving_kcal = EXCLUDED.per_serving_kcal, "
        "per_serving_protein = EXCLUDED.per_serving_protein, per_serving_carb = EXCLUDED.per_serving_carb, "
        "per_serving_fat = EXCLUDED.per_serving_fat, per_serving_fiber = EXCLUDED.per_serving_fiber, "
        "per_serving_sugar = EXCLUDED.per_serving_sugar, per_serving_sodium_mg = EXCLUDED.per_serving_sodium_mg, "
        "total_kcal = EXCLUDED.total_kcal, coverage_ratio = EXCLUDED.coverage_ratio, "
        "unverified_share = EXCLUDED.unverified_share, reference_version = EXCLUDED.reference_version, "
        "computed_at = now()",
        [recipe_id, *(rounded(ps[n], 2) for n in NUTRIENTS), rounded(result["total_kcal"], 2),
         rounded(result["coverage"], 3), rounded(result["unverified"], 3), REFERENCE_VERSION])
    return recipe_id
