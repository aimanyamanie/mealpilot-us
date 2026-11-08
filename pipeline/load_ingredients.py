"""units.csv + ingredients.csv + extra_portions.csv + USDA records -> database.

    python load_ingredients.py

Safe to re-run: upserts by slug. USDA records are cached in data/usda/.
"""
import csv
from fractions import Fraction

import usda
from db import connect
from measures import HERE, load_units, parse_usda_portion, portion_grams


def read_csv(name):
    with open(HERE / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def truthy(v):
    return str(v).strip().lower() in ("true", "yes", "1", "y")


def usda_portions(food, units):
    """Unique (unit, qualifier) -> (grams per unit, label). Keeps the largest measure
    when USDA lists the same one twice ('1 clove', '3 cloves')."""
    out = {}
    for p in food.get("foodPortions", []):
        unit_name = (p.get("measureUnit") or {}).get("name") or ""
        if unit_name == "undetermined":
            unit_name = ""
        parsed = parse_usda_portion(p.get("amount") or 1, unit_name, p.get("modifier"), units)
        if not parsed:
            continue
        unit, qualifier, amount = parsed
        g = portion_grams(amount, p["gramWeight"])
        label = f"USDA {food['fdcId']}: {amount:g} {p.get('modifier') or unit_name} = {p['gramWeight']} g"
        key = (unit, qualifier)
        if key in out:
            old = out[key][0]
            if abs(old - g) / old > Fraction(2, 100):
                print(f"  ! {food['description']}: two '{unit} {qualifier}' weights, "
                      f"{float(old):.2f} g and {float(g):.2f} g; keeping the larger measure")
            if amount <= out[key][2]:
                continue
        out[key] = (g, label, amount)
    return {k: (g, label) for k, (g, label, _) in out.items()}


def main():
    units = load_units()
    rows = read_csv("ingredients.csv")
    extras = read_csv("extra_portions.csv")
    foods = usda.get_foods(sorted({int(r["fdc_id"]) for r in rows}))

    with connect() as conn, conn.cursor() as cur:
        for code, u in units.items():
            cur.execute("""insert into units (code, kind, grams, ml, aliases) values (%s,%s,%s,%s,%s)
                on conflict (code) do update set kind=excluded.kind, grams=excluded.grams,
                    ml=excluded.ml, aliases=excluded.aliases""",
                        (code, u["kind"], u["grams"] and float(u["grams"]),
                         u["ml"] and float(u["ml"]), u["aliases"]))

        for r in rows:
            food = foods[int(r["fdc_id"])]
            nut = usda.nutrients(food)
            for num, (name, unit, _) in nut.items():
                cur.execute("""insert into nutrients (number, name, unit) values (%s,%s,%s)
                    on conflict (number) do nothing""", (num, name, unit))

            cur.execute("""insert into ingredients (slug, name, category, food_group, gluten,
                    animal_rennet, alcohol, fdc_id, fdc_description, fdc_data_type, pick_note)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (slug) do update set name=excluded.name, category=excluded.category,
                    food_group=excluded.food_group, gluten=excluded.gluten,
                    animal_rennet=excluded.animal_rennet, alcohol=excluded.alcohol,
                    fdc_id=excluded.fdc_id, fdc_description=excluded.fdc_description,
                    fdc_data_type=excluded.fdc_data_type, pick_note=excluded.pick_note,
                    -- a sign-off covers one USDA record; picking another voids it
                    reviewed_by = case when ingredients.fdc_id = excluded.fdc_id
                                       then ingredients.reviewed_by end,
                    reviewed_at = case when ingredients.fdc_id = excluded.fdc_id
                                       then ingredients.reviewed_at end,
                    updated_at = now()
                returning id""",
                        (r["slug"], r["name"], r["category"], r["food_group"], truthy(r["gluten"]),
                         truthy(r["animal_rennet"]), truthy(r["alcohol"]), int(r["fdc_id"]),
                         food["description"], food["dataType"], r["pick_note"] or None))
            iid = cur.fetchone()[0]

            cur.execute("delete from ingredient_aliases where ingredient_id = %s", (iid,))
            for a in {a.strip().lower() for a in r["aliases"].split(";") if a.strip()}:
                cur.execute("insert into ingredient_aliases values (%s, %s)", (a, iid))

            cur.execute("delete from ingredient_allergens where ingredient_id = %s", (iid,))
            for a in [a.strip() for a in r["allergens"].split(";") if a.strip()]:
                cur.execute("insert into ingredient_allergens values (%s, %s)", (iid, a))

            cur.execute("delete from ingredient_nutrients where ingredient_id = %s", (iid,))
            for num, (_, _, amt) in nut.items():
                cur.execute("insert into ingredient_nutrients values (%s, %s, %s)", (iid, num, amt))

            ports = {k: (g, label, food["fdcId"]) for k, (g, label) in usda_portions(food, units).items()}
            for e in extras:
                if e["ingredient"] == r["slug"]:
                    ports[(e["unit"], e["qualifier"])] = (Fraction(e["grams_per_unit"]),
                                                          e["source_note"], int(e["source_fdc_id"]))
            keep = []
            for (unit, qualifier), (g, note, src) in ports.items():
                cur.execute("""insert into ingredient_portions
                        (ingredient_id, unit, qualifier, grams_per_unit, source_fdc_id, source_note)
                    values (%s,%s,%s,%s,%s,%s)
                    on conflict (ingredient_id, unit, qualifier) do update set
                        grams_per_unit=excluded.grams_per_unit, source_fdc_id=excluded.source_fdc_id,
                        source_note=excluded.source_note
                    returning id""", (iid, unit, qualifier, float(g), src, note))
                keep.append(cur.fetchone()[0])
            # fails if a recipe still uses a portion that is gone: reload that recipe
            cur.execute("delete from ingredient_portions where ingredient_id = %s and id <> all(%s)",
                        (iid, keep))
            print(f"{r['slug']:<22} {food['fdcId']:>8}  {food['description'][:55]:<55} "
                  f"{len(nut):>3} nutrients, {len(ports)} portions")
    print(f"\n{len(rows)} ingredients loaded.")


if __name__ == "__main__":
    main()
