"""Load recipe cards into recipes, lines, steps and nutrition.

    python load_cards.py sip-and-feast            # data/cards/sip-and-feast/*.json -> main
    python load_cards.py --test tests/cards       # our own sample cards -> dev-youtube-test

main requires the creator to have granted recipe_data in permissions.csv.
--test writes to the dev-youtube-test branch only (youtube_test.connect),
for cards we wrote ourselves; those creators stay permission 'none'.

Every recipe is saved as status 'in_review' with the reasons it cannot be
published yet. A card's own calorie figure is a cross-check only: when it
differs from ours by more than 25%, the recipe is held for a look.
"""
import argparse
import json
import os
import re
from fractions import Fraction
from pathlib import Path

import psycopg
from dotenv import load_dotenv

import youtube_test
from parse_card import find_recipe, parse_card
from parse_recipe import load_vocab
from permissions import granted
from recipe_store import COVERAGE_MIN, dec, load_reference, nutrition, prepare_lines, save_recipe

HERE = Path(__file__).resolve().parent
CARDS = HERE / "data" / "cards"
KCAL_TOLERANCE = 0.25


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def upsert_creator(conn, slug, name, status) -> int:
    return conn.execute(
        "INSERT INTO creators (slug, display_name, permission_status) VALUES (%s, %s, %s) "
        "ON CONFLICT (slug) DO UPDATE SET permission_status = EXCLUDED.permission_status, "
        "updated_at = now() RETURNING id", [slug, name, status]).fetchone()[0]


def hold_reasons(card, result, licensed: bool) -> list[str]:
    hold = []
    if not card["servings"]:
        hold.append("servings_unknown")
    if result["coverage"] < COVERAGE_MIN:
        hold.append("coverage_below_90")
    hold += result["held"]
    ours, theirs = result["per_serving"]["kcal"], card["creator_kcal"]
    if ours is not None and theirs:
        if abs(float(ours) - theirs) / theirs > KCAL_TOLERANCE:
            hold.append("kcal_differs_from_creator")
    if not card["steps"]:
        hold.append("no_steps")
    else:
        hold.append("steps_not_rewritten")
    if not card["recipe_type"]:
        hold.append("category_unknown")
    if not card["video_id"]:
        hold.append("no_video")
    hold += ["meal_prep_fields_missing", "nutrition_unreviewed"]
    if not licensed:
        hold.append("no_licence")
    return hold


def load_card(conn, creator_id, creator_slug, recipe, vocab, ref, licensed, page=None):
    card = parse_card(recipe, vocab)
    servings = Fraction(card["servings"]) if card["servings"] else Fraction(1)
    lines = prepare_lines(card["lines"], ref)
    result = nutrition(lines, ref[1], servings)
    video = card["video_id"]
    if video and conn.execute("SELECT 1 FROM recipes WHERE video_id = %s AND slug <> %s",
                              [video, f"{creator_slug}-{slugify(card['title'])}"]).fetchone():
        video = None          # the same video already belongs to another recipe row
    notes = f"creator states {card['creator_kcal']:g} kcal/serving" if card["creator_kcal"] else None
    save_recipe(conn, {
        "slug": f"{creator_slug}-{slugify(card['title'])}", "market": "US", "title": card["title"],
        "creator_id": creator_id, "cuisine": card["cuisine"], "recipe_type": card["recipe_type"],
        "meal_slots": card["meal_slots"],
        "plannable": card["recipe_type"] == "meal" and bool(card["meal_slots"]),
        "video_id": video, "video_url": f"https://www.youtube.com/watch?v={video}" if video else None,
        "recipe_page_url": card["url"] or page, "thumbnail_url": card["image"],
        "published_on": card["published_on"], "source_servings": dec(servings),
        "servings_confidence": "stated" if card["servings"] else "guess",
        "servings_evidence": card["servings_evidence"],
        "prep_minutes": card["prep_minutes"], "cook_minutes": card["cook_minutes"],
        "status": "in_review", "hold_reasons": hold_reasons(card, result, licensed),
        "review_notes": notes,
    }, lines, ref, result, steps=card["steps"])
    return card, result


def cards_in(folder: Path):
    for path in sorted(folder.glob("*.json")):
        blob = json.loads(path.read_text(encoding="utf-8"))
        recipe = find_recipe(blob.get("recipe", blob)) if isinstance(blob, dict) else find_recipe(blob)
        if recipe:
            yield path, recipe, (blob.get("source") if isinstance(blob, dict) else None)


def report(card, result, path):
    ps = result["per_serving"]
    kcal = f"{float(ps['kcal']):.0f}" if ps["kcal"] is not None else "-"
    theirs = f" (card says {card['creator_kcal']:g})" if card["creator_kcal"] else ""
    print(f"  {path.name}: {card['title']!r}, serves {card['servings'] or '?'}, "
          f"{len(card['lines'])} lines, coverage {float(result['coverage']):.0%}, "
          f"{kcal} kcal/serving{theirs}, {len(card['steps'])} steps")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("creator", nargs="?", help="creator slug: loads data/cards/<slug>/ into main")
    ap.add_argument("--test", type=Path, help="folder of our own sample cards -> dev-youtube-test")
    args = ap.parse_args(argv)
    vocab = load_vocab()
    if args.test:
        conn = youtube_test.connect()
        groups = {"mealpilot-test-kitchen": args.test}
        names, licensed = {"mealpilot-test-kitchen": "MealPilot Test Kitchen"}, False
        statuses = {"mealpilot-test-kitchen": "none"}
    elif args.creator:
        row = granted(args.creator)
        load_dotenv(HERE.parent / ".env")
        conn = psycopg.connect(os.environ["DATABASE_URL"])
        groups = {args.creator: CARDS / args.creator}
        names, licensed = {args.creator: row["display_name"]}, True
        statuses = {args.creator: "granted"}
    else:
        ap.error("give a creator slug, or --test <folder>")
    with conn:
        ref = load_reference(conn)
        for slug, folder in groups.items():
            with conn.transaction():
                creator_id = upsert_creator(conn, slug, names[slug], statuses[slug])
                print(f"{slug}:")
                for path, recipe, page in cards_in(folder):
                    card, result = load_card(conn, creator_id, slug, recipe, vocab, ref, licensed, page)
                    report(card, result, path)


if __name__ == "__main__":
    main()
