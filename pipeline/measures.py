"""Units, USDA household portions, and line quantities to grams.

Grams lookup order for a recipe line:
  1. a mass unit (lb, oz, g): exact conversion;
  2. the ingredient's portion for that unit (and qualifier, when given);
  3. a volume unit with no portion of its own: scale another volume portion of the
     same ingredient (same qualifier) by millilitres.
Anything else is unknown: grams stay None, never 0.
"""
import csv
import re
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).parent


def load_units(path=HERE / "units.csv"):
    units = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            units[row["code"]] = {
                "kind": row["kind"],
                "grams": Fraction(row["grams"]) if row["grams"] else None,
                "ml": Fraction(row["ml"]) if row["ml"] else None,
                "aliases": [a for a in row["aliases"].split(";") if a],
            }
    return units


def unit_lookup(units):
    """lower-case spelling -> unit code."""
    out = {}
    for code, u in units.items():
        out[code.lower()] = code
        for a in u["aliases"]:
            out[a.lower()] = code
    return out


def to_fraction(q):
    """'1/2', '1 1/2', 0.25, 4 -> Fraction."""
    if q is None:
        return None
    if isinstance(q, (int, Fraction)):
        return Fraction(q)
    if isinstance(q, float):
        return Fraction(str(q))
    parts = str(q).strip().split()
    return sum((Fraction(p) for p in parts), Fraction(0))


def parse_usda_portion(amount, unit_name, modifier, units):
    """A USDA foodPortion -> (unit code, qualifier, grams for ONE unit) or None.

    SR Legacy puts the measure in `modifier` ("cup, fluid (yields 2 cups whipped)",
    "thigh with skin", "tbsp, ground"); Foundation uses measureUnit. The qualifier is
    everything after the unit word and is kept, because it decides the weight
    (a whipped cup of cream is 120 g, a fluid cup 238 g).
    """
    lookup = unit_lookup(units)
    text = (modifier or "").strip() or (unit_name or "").strip()
    low = text.lower()
    for spelling in sorted(lookup, key=len, reverse=True):     # 'fl oz' before 'oz'
        if re.match(re.escape(spelling) + r"(?=$|[\s,(])", low):
            code = lookup[spelling]
            if units[code]["kind"] == "mass":
                return None                                    # mass needs no portion
            return code, text[len(spelling):].strip(" ,"), amount
    return None


def portion_grams(amount, gram_weight):
    return Fraction(str(gram_weight)) / Fraction(str(amount or 1))


class GramsError(ValueError):
    pass


def resolve_grams(quantity, unit, qualifier, portions, units):
    """-> (grams, method, portion key) for one line.

    portions: list of dicts {unit, qualifier, grams_per_unit, key} for the ingredient.
    Raises GramsError when the answer would be a guess or is ambiguous.
    """
    if quantity is None:
        return None, None, None
    q = to_fraction(quantity)
    if unit is None:
        raise GramsError("no unit: say 'whole', 'medium', 'clove'... or give a weight")
    if unit not in units:
        raise GramsError(f"unknown unit {unit!r}")
    u = units[unit]
    if u["kind"] == "mass":
        return q * u["grams"], "mass", None

    def pick(cands):
        if qualifier:
            cands = [p for p in cands if qualifier.lower() in p["qualifier"].lower()]
            return cands
        plain = [p for p in cands if not p["qualifier"]]
        return plain or cands

    same = pick([p for p in portions if p["unit"] == unit])
    if len(same) == 1:
        return q * same[0]["grams_per_unit"], "portion", same[0]["key"]
    if len(same) > 1:
        labels = ", ".join(repr(p["qualifier"]) for p in same)
        raise GramsError(f"{unit}: several portions ({labels}); set a qualifier")

    if u["kind"] == "volume":
        vols = pick([p for p in portions if units[p["unit"]]["kind"] == "volume"])
        if vols:
            # prefer the largest measure: a cup weighs more precisely than a dash
            base = max(vols, key=lambda p: units[p["unit"]]["ml"])
            per_ml = base["grams_per_unit"] / units[base["unit"]]["ml"]
            return q * u["ml"] * per_ml, "volume_scaled", base["key"]
    raise GramsError(f"no {unit!r} portion{' (' + qualifier + ')' if qualifier else ''} "
                     "for this ingredient: add one to extra_portions.csv with its source")
