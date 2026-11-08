"""recipes/<slug>.json (extracted from a transcript) -> database.

    python load_recipe.py recipes/chicken-alfredo-joshua-weissman.json
    python load_recipe.py --check recipes/*.json      # validate only, no writes

Checks before writing:
  * every ingredient slug exists and every quoted piece of evidence is really in
    the transcript, near the timestamp given (catches invented quotes);
  * every counted line converts to grams (otherwise the recipe loads as 'draft',
    and its nutrition shows as unknown).
Re-running replaces the recipe's lines and steps; the recipe keeps its id.
"""
import hashlib
import json
import re
import sys
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

from db import connect
from measures import HERE, GramsError, load_units, resolve_grams, to_fraction

EVIDENCE_WINDOW_SEC = 20


def dec(f):
    if f is None:
        return None
    with localcontext() as c:
        c.prec = 30
        return Decimal(f.numerator) / Decimal(f.denominator)


def norm(s):
    return re.sub(r"[^a-z0-9']+", " ", s.lower()).strip()


def check_evidence(lines, segments):
    """Each '...'-separated piece of every evidence quote must appear in the transcript,
    starting within EVIDENCE_WINDOW_SEC of the line's timestamp."""
    text, starts = "", []
    for seg in segments:
        piece = norm(seg["text"]) + " "
        starts.append((len(text), seg["start"]))
        text += piece
    errors = []
    for ln in lines:
        ev, t = ln.get("evidence"), ln.get("t")
        if not ev:
            errors.append(f"{ln['text']!r}: no evidence quote")
            continue
        for piece in [norm(p) for p in ev.split("...") if norm(p)]:
            hits = [m.start() for m in re.finditer(re.escape(piece), text)]
            times = [max(s for pos, s in starts if pos <= h) for h in hits]
            if not times:
                errors.append(f"{ln['text']!r}: {piece!r} is not in the transcript")
            elif t is not None and min(abs(x - t) for x in times) > EVIDENCE_WINDOW_SEC:
                errors.append(f"{ln['text']!r}: {piece!r} is at {times}, not near {t}s")
    return errors


def main(paths, write=True):
    units = load_units()
    conn = connect()
    cur = conn.cursor()
    cur.execute("select slug, id from ingredients")
    ing = dict(cur.fetchall())
    cur.execute("select id, ingredient_id, unit, qualifier, grams_per_unit from ingredient_portions")
    portions = {}
    for pid, iid, unit, qual, g in cur.fetchall():
        portions.setdefault(iid, []).append(
            {"key": pid, "unit": unit, "qualifier": qual, "grams_per_unit": Fraction(str(g))})

    failed = False
    for path in paths:
        rec = json.loads(Path(path).read_text(encoding="utf-8"))
        tpath = HERE / rec["source"]["transcript_file"]
        traw = tpath.read_bytes()
        tr = json.loads(traw)
        print(f"\n== {rec['slug']}  ({tr['metadata']['title']})")

        problems = check_evidence(rec["ingredients"], tr["transcript"])
        lines, unknown = [], 0
        for pos, ln in enumerate(rec["ingredients"], 1):
            iid = ing.get(ln["ingredient"])
            if iid is None:
                problems.append(f"{ln['text']!r}: ingredient {ln['ingredient']!r} is not loaded")
            counted = ln.get("in_nutrition", True)
            grams = method = pid = None
            try:
                grams, method, pid = resolve_grams(ln.get("quantity"), ln.get("unit"),
                                                   ln.get("qualifier"), portions.get(iid, []), units)
            except GramsError as e:
                print(f"  ! {ln['text']}: {e}")
            if counted and (grams is None or iid is None):
                unknown += 1
            lines.append((pos, ln, iid, grams, method, pid, counted))
            print(f"  {pos:>2}. {ln['text']:<48} {ln['basis']:<9} "
                  f"{(f'{float(grams):8.1f} g' if grams is not None else '       ? g')}"
                  f"{'' if counted else '   (not counted: ' + ln['excluded_reason'][:40] + ')'}")
        for p in problems:
            print("  ERROR", p)
        if problems:
            failed = True
            continue
        status = "draft" if unknown else "needs_review"
        if not write:
            print(f"  ok: would load as {status}")
            continue

        ch = rec["chef"]
        cur.execute("""insert into chefs (slug, name, youtube_channel_id, youtube_url, website_url, market)
            values (%s,%s,%s,%s,%s,%s)
            on conflict (slug) do update set name=excluded.name,
                youtube_channel_id=excluded.youtube_channel_id, youtube_url=excluded.youtube_url,
                website_url=excluded.website_url
            returning id""", (ch["slug"], ch["name"], ch.get("youtube_channel_id"),
                              ch.get("youtube_url"), ch.get("website_url"), rec["market"]))
        chef_id = cur.fetchone()[0]

        md = tr["metadata"]
        cur.execute("""insert into sources (chef_id, kind, video_id, title, url, thumbnail_url,
                length_seconds, language, transcript, transcript_sha256)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (video_id) do update set title=excluded.title, url=excluded.url,
                thumbnail_url=excluded.thumbnail_url, length_seconds=excluded.length_seconds,
                language=excluded.language, transcript=excluded.transcript,
                transcript_sha256=excluded.transcript_sha256
            returning id""",
                    (chef_id, rec["source"]["kind"], tr["video_id"], md["title"],
                     f"https://www.youtube.com/watch?v={tr['video_id']}", md.get("thumbnail_url"),
                     tr.get("length_seconds"), tr.get("language"), json.dumps(tr),
                     hashlib.sha256(traw).hexdigest()))
        source_id = cur.fetchone()[0]

        cur.execute("""insert into recipes (slug, market, chef_id, source_id, title, summary, cuisine,
                course, meal_slots, servings, servings_basis, prep_minutes, cook_minutes,
                times_basis, difficulty, notes, status, extracted_by)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (slug) do update set market=excluded.market, chef_id=excluded.chef_id,
                source_id=excluded.source_id, title=excluded.title, summary=excluded.summary,
                cuisine=excluded.cuisine, course=excluded.course, meal_slots=excluded.meal_slots,
                servings=excluded.servings, servings_basis=excluded.servings_basis,
                prep_minutes=excluded.prep_minutes, cook_minutes=excluded.cook_minutes,
                times_basis=excluded.times_basis, difficulty=excluded.difficulty,
                notes=excluded.notes, status=excluded.status, extracted_by=excluded.extracted_by,
                extracted_at=now(), reviewed_by=null, reviewed_at=null
            returning id""",
                    (rec["slug"], rec["market"], chef_id, source_id, rec["title"], rec.get("summary"),
                     rec.get("cuisine"), rec.get("course"), rec.get("meal_slots", []),
                     dec(to_fraction(rec["servings"])), rec["servings_basis"], rec.get("prep_minutes"),
                     rec.get("cook_minutes"), rec.get("times_basis"), rec.get("difficulty"),
                     rec.get("notes"), status, rec["extracted_by"]))
        rid = cur.fetchone()[0]

        cur.execute("delete from recipe_ingredients where recipe_id = %s", (rid,))
        cur.execute("delete from recipe_steps where recipe_id = %s", (rid,))
        for pos, ln, iid, grams, method, pid, counted in lines:
            cur.execute("""insert into recipe_ingredients (recipe_id, position, group_label,
                    ingredient_id, display_text, quantity, unit, qualifier, preparation,
                    quantity_basis, grams, grams_method, portion_id, in_nutrition,
                    excluded_reason, optional, evidence, evidence_sec)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (rid, pos, ln.get("group"), iid, ln["text"], dec(to_fraction(ln.get("quantity"))),
                         ln.get("unit"), ln.get("qualifier"), ln.get("preparation"), ln["basis"],
                         dec(grams), method, pid, counted, ln.get("excluded_reason"),
                         ln.get("optional", False), ln.get("evidence"), ln.get("t")))
        for n, st in enumerate(rec["steps"], 1):
            cur.execute("insert into recipe_steps values (%s,%s,%s,%s)", (rid, n, st["text"], st.get("t")))
        conn.commit()
        print(f"  loaded as {status} (recipe id {rid})")
    conn.close()
    return 1 if failed else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    check = "--check" in args
    sys.exit(main([a for a in args if a != "--check"], write=not check))
