"""TEST ONLY: parse fetched YouTube descriptions into recipes on the
dev-youtube-test branch, with grams, nutrition and coverage.

    python fetch_youtube.py && python load_recipes.py

Writes only through youtube_test.connect(), which refuses main. Creators
stay permission_status = 'none', so v_published_recipes shows nothing.
The grams and nutrition rules live in recipe_store.py, shared with
load_cards.py.
"""
import json
from collections import Counter
from fractions import Fraction

from parse_recipe import load_vocab, parse_description
from recipe_store import COVERAGE_MIN, dec, load_reference, nutrition, prepare_lines, save_recipe
from youtube_test import DATA, connect

MIN_LINES = 3


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
    parsed = parse_description(video["description"], vocab)
    if len(parsed["lines"]) < MIN_LINES:
        stats["not_a_recipe"] += 1
        return
    servings = Fraction(parsed["servings"]) if parsed["servings"] else Fraction(1)
    lines = prepare_lines(parsed["lines"], ref)
    for line in lines:
        if line["ingredient"] is None:
            stats["unmatched_terms"][line["raw_text"].lower()[:60]] += 1
    result = nutrition(lines, ref[1], servings)
    hold = [] if parsed["servings"] else ["servings_unknown"]
    if result["coverage"] < COVERAGE_MIN:
        hold.append("coverage_below_90")
    hold += result["held"] + ["nutrition_unreviewed", "no_licence"]
    save_recipe(conn, {
        "slug": f"{creator_slug}-{video['video_id']}".lower(), "market": "US",
        "title": video["title"], "creator_id": creator_id, "video_id": video["video_id"],
        "video_url": f"https://www.youtube.com/watch?v={video['video_id']}",
        "thumbnail_url": video["thumbnail_url"], "video_duration_seconds": video["duration_seconds"],
        "video_checked_at": video["fetched_at"], "published_on": video["published_at"][:10],
        "source_servings": dec(servings),
        "servings_confidence": "stated" if parsed["servings"] else "guess",
        "servings_evidence": parsed["servings_evidence"], "status": "in_review",
        "hold_reasons": hold,
    }, lines, ref, result)
    stats["recipes"] += 1
    stats["lines"] += len(lines)
    stats["matched"] += sum(1 for l in lines if l["ingredient"])
    stats["with_grams"] += sum(1 for l in lines if l["grams_edible"] is not None)
    stats["servings_stated"] += 1 if parsed["servings"] else 0
    stats["coverage_ok"] += 1 if result["coverage"] >= COVERAGE_MIN else 0


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
