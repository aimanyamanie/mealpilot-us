"""TEST ONLY: parse fetched YouTube descriptions into recipes on the
dev-youtube-test branch, with grams, nutrition and coverage.

    python fetch_youtube.py && python load_recipes.py

Writes only through youtube_test.connect(), which refuses main. Creators
stay permission_status = 'none', so v_published_recipes shows nothing.

Grams per line, in the order CLAUDE.md sets: a mass unit; a stated package
size ("1 (15 oz) can"); the exact ingredient_portions row; that unit's
default portion; density for a volume unit. Otherwise NULL, and the line
counts against coverage.

A range ("2-3 cloves") uses the lower bound. A nutrient the ingredient
table lacks (USDA publishes no sugar for shrimp) is ignored when those
lines are under 1% of the recipe's grams; otherwise that per-serving value
is NULL and the recipe is held.
"""
import json
from collections import Counter
from decimal import Decimal
from fractions import Fraction

from parse_recipe import load_vocab, parse_description
from youtube_test import DATA, connect

MIN_LINES = 3
COVERAGE_MIN = Fraction(9, 10)
NUTRIENTS = ["kcal", "protein", "carb", "fat", "fiber", "sugar", "sodium_mg"]
NEGLIGIBLE_SHARE = Fraction(1, 100)


def frac(v):
    return None if v is None else Fraction(str(v))


def dec(v, places=3):
    return None if v is None else Decimal(v.numerator) / Decimal(v.denominator) if isinstance(v, Fraction) else v


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


def grams_for(line, units, ingredients, portions, defaults):
    """(grams as purchased, method) or (None, reason)."""
    q = line["quantity"]
    if q is None:
        return None, None
    unit = line["unit"] or "piece"
    kind = units[unit][1]
    if kind == "subjective":
        return None, None
    if kind == "mass":
        return q * units[unit][2], "mass"
    if line["package_grams"] is not None:
        return q * line["package_grams"], "mass"
    slug = line["ingredient"]
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
    coverage = Fraction(len([l for l in stated if l["grams_edible"] is not None]), len(stated)) if stated else Fraction(0)
    unverified = (sum((l["grams_edible"] for l in computed if ingredients[l["ingredient"]]["unverified"]),
                      Fraction(0)) / total_grams) if total_grams else None
    total_kcal = per_serving["kcal"] * servings if per_serving["kcal"] is not None else None
    return per_serving, coverage, unverified, total_kcal, held


def upsert_creator(conn, c) -> int:
    return conn.execute(
        "INSERT INTO creators (slug, display_name, channel_id, channel_name, channel_url, "
        "avatar_url, subscriber_count, permission_status) VALUES (%s,%s,%s,%s,%s,%s,%s,'none') "
        "ON CONFLICT (slug) DO UPDATE SET display_name = EXCLUDED.display_name, "
        "subscriber_count = EXCLUDED.subscriber_count, avatar_url = EXCLUDED.avatar_url, "
        "updated_at = now() RETURNING id",
        [c["slug"], c["display_name"], c["channel_id"], c["title"],
         f"https://www.youtube.com/{c['handle']}", c["avatar_url"], c["subscriber_count"]],
    ).fetchone()[0]


def load_video(conn, creator_id, creator_slug, video, vocab, ref, stats):
    units, ingredients, portions, defaults = ref
    parsed = parse_description(video["description"], vocab)
    if len(parsed["lines"]) < MIN_LINES:
        stats["not_a_recipe"] += 1
        return
    servings = Fraction(parsed["servings"]) if parsed["servings"] else Fraction(1)
    hold = [] if parsed["servings"] else ["servings_unknown"]
    lines = []
    for order, line in enumerate(parsed["lines"]):
        grams, how = grams_for(line, units, ingredients, portions, defaults)
        kind = units[line["unit"] or "piece"][1]
        line["counts_for_coverage"] = line["quantity"] is not None and kind != "subjective"
        line["grams_as_purchased"] = grams
        edible = ingredients[line["ingredient"]]["edible_pct"] if line["ingredient"] else Fraction(100)
        line["grams_edible"] = grams * edible / 100 if grams is not None else None
        line["grams_method"] = how if grams is not None else None
        line["review_reason"] = None if grams is not None or not line["counts_for_coverage"] else how
        if line["ingredient"] is None:
            line["review_reason"] = "unmatched_ingredient"
            stats["unmatched_terms"][line["raw_text"].lower()[:60]] += 1
        line["display_order"] = order
        lines.append(line)
    per_serving, coverage, unverified, total_kcal, held = nutrition(lines, ingredients, servings)
    if coverage < COVERAGE_MIN:
        hold.append("coverage_below_90")
    hold += held + ["nutrition_unreviewed", "no_licence"]

    recipe_id = conn.execute(
        "INSERT INTO recipes (slug, market, title, creator_id, video_id, video_url, thumbnail_url, "
        "video_duration_seconds, video_checked_at, published_on, source_servings, "
        "servings_confidence, servings_evidence, status, hold_reasons) "
        "VALUES (%s,'US',%s,%s,%s,%s,%s,%s,%s,%s::date,%s,%s,%s,'in_review',%s) "
        "ON CONFLICT (video_id) DO UPDATE SET title = EXCLUDED.title, "
        "thumbnail_url = EXCLUDED.thumbnail_url, video_checked_at = EXCLUDED.video_checked_at, "
        "source_servings = EXCLUDED.source_servings, servings_confidence = EXCLUDED.servings_confidence, "
        "servings_evidence = EXCLUDED.servings_evidence, hold_reasons = EXCLUDED.hold_reasons, "
        "updated_at = now() RETURNING id",
        [f"{creator_slug}-{video['video_id']}".lower(), video["title"], creator_id, video["video_id"],
         f"https://www.youtube.com/watch?v={video['video_id']}", video["thumbnail_url"],
         video["duration_seconds"], video["fetched_at"], video["published_at"][:10],
         dec(servings), "stated" if parsed["servings"] else "guess",
         parsed["servings_evidence"], hold],
    ).fetchone()[0]
    conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = %s", [recipe_id])
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO recipe_ingredients (recipe_id, display_order, raw_text, group_label, quantity, "
            "quantity_max, unit_id, modifier, ingredient_id, preparation_note, is_optional, is_scalable, "
            "grams_as_purchased, grams_edible, grams_method, needs_review, review_reason) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [[recipe_id, l["display_order"], l["raw_text"], l["group_label"], dec(l["quantity"]),
              dec(l["quantity_max"]), units[l["unit"]][0] if l["unit"] else None, l["modifier"],
              ingredients[l["ingredient"]]["id"] if l["ingredient"] else None, l["preparation_note"],
              l["is_optional"], l["is_scalable"], dec(l["grams_as_purchased"]), dec(l["grams_edible"]),
              l["grams_method"], l["review_reason"] is not None, l["review_reason"]] for l in lines])
    conn.execute(
        "INSERT INTO recipe_nutrition (recipe_id, per_serving_kcal, per_serving_protein, per_serving_carb, "
        "per_serving_fat, per_serving_fiber, per_serving_sugar, per_serving_sodium_mg, total_kcal, "
        "coverage_ratio, unverified_share, reference_version, computed_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'FDC Foundation 2026-10 + SR Legacy 2018-04',now()) "
        "ON CONFLICT (recipe_id) DO UPDATE SET per_serving_kcal = EXCLUDED.per_serving_kcal, "
        "per_serving_protein = EXCLUDED.per_serving_protein, per_serving_carb = EXCLUDED.per_serving_carb, "
        "per_serving_fat = EXCLUDED.per_serving_fat, per_serving_fiber = EXCLUDED.per_serving_fiber, "
        "per_serving_sugar = EXCLUDED.per_serving_sugar, per_serving_sodium_mg = EXCLUDED.per_serving_sodium_mg, "
        "total_kcal = EXCLUDED.total_kcal, coverage_ratio = EXCLUDED.coverage_ratio, "
        "unverified_share = EXCLUDED.unverified_share, computed_at = now()",
        [recipe_id, *(round(dec(per_serving[n]), 2) if per_serving[n] is not None else None for n in NUTRIENTS),
         round(dec(total_kcal), 2) if total_kcal is not None else None,
         round(dec(coverage), 3), round(dec(unverified), 3) if unverified is not None else None])
    stats["recipes"] += 1
    stats["lines"] += len(lines)
    stats["matched"] += sum(1 for l in lines if l["ingredient"])
    stats["with_grams"] += sum(1 for l in lines if l["grams_edible"] is not None)
    stats["servings_stated"] += 1 if parsed["servings"] else 0
    stats["coverage_ok"] += 1 if coverage >= COVERAGE_MIN else 0


def main() -> None:
    files = sorted(DATA.glob("*.json"))
    if not files:
        raise SystemExit("No fetched channels in data/youtube/: run fetch_youtube.py first.")
    vocab = load_vocab()
    with connect() as conn:
        ref = load_reference(conn)
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            c = data["creator"]
            stats = Counter(unmatched_terms=Counter())
            with conn.transaction():
                creator_id = upsert_creator(conn, c)
                for video in data["videos"]:
                    load_video(conn, creator_id, c["slug"], video, vocab, ref, stats)
            lines = stats["lines"] or 1
            print(f"{c['slug']}: {len(data['videos'])} videos, {stats['recipes']} recipes "
                  f"({stats['not_a_recipe']} not recipes), {stats['lines']} lines, "
                  f"matched {stats['matched'] / lines:.0%}, grams {stats['with_grams'] / lines:.0%}, "
                  f"servings stated {stats['servings_stated']}, coverage>=90% {stats['coverage_ok']}")
            for term, n in stats["unmatched_terms"].most_common(8):
                print(f"    unmatched x{n}: {term}")


if __name__ == "__main__":
    main()
