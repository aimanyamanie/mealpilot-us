"""English recipe text -> ingredient lines and servings.

Pure functions, no database. The vocabulary comes from units.csv and
ingredients_seed.csv, matched longest-first, so a missing alias shows up
as an unmatched line rather than a wrong match.

    parse_description(text, vocab) -> {"servings": ..., "lines": [...]}
    parse_line(text, vocab)        -> one parsed line

Every bug found in real text becomes a case in tests/golden_lines.json.
"""
import csv
import re
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent

UNICODE_FRACTIONS = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4",
                     "⅕": "1/5", "⅖": "2/5", "⅗": "3/5", "⅘": "4/5", "⅙": "1/6",
                     "⅚": "5/6", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"}
SIZES = ["extra large", "extra-large", "jumbo", "large", "medium", "small"]
PREP_FOR_VOLUME = ["chopped", "sliced", "diced", "minced", "shredded", "grated",
                   "packed", "cubed", "mashed", "crumbled", "slivered", "ground"]
CONTAINERS = {"can", "jar", "package", "bag", "box", "container", "stick"}
WORD_QUANTITIES = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
                   "five": 5, "six": 6, "half": Fraction(1, 2), "a half": Fraction(1, 2)}

NUM = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?|\.\d+)"
QTY = re.compile(rf"^(?P<q>{NUM})(?:\s*(?:-|–|to)\s*(?P<q2>{NUM}))?\s*")
PAREN_SIZE = re.compile(rf"^\((?P<n>{NUM})\s*-?\s*(?P<u>oz|ounce|ounces|g|grams?|lb|lbs?|ml|fl\.?\s*oz)\.?\)\s*", re.I)
BULLET = re.compile(r"^\s*(?:[-–•*▢◦●▪✓✔]|\d+[.)]\s+(?=\D))\s*")
HEADING = re.compile(r"^\s*(?:ingredients?|what you(?:'|’)?ll need|you(?:'|’)?ll need|shopping list)\b[^a-z]*$", re.I)
GROUP = re.compile(r"^\s*(?:for\s+(?:the\s+)?[\w\s&-]{2,30}|[\w\s&-]{2,30}\s+ingredients?)\s*:?\s*$", re.I)
STOP = re.compile(r"^\s*(?:instructions?|directions?|method|steps?|how to make|equipment|"
                  r"tools|notes?|nutrition|timestamps?|chapters?|links?|follow|subscribe|"
                  r"music|shop|products?|get the|full recipe|printable|connect|"
                  r"\d{1,2}:\d{2})\b", re.I)
SERVINGS = re.compile(r"\b(?:serves|servings?|makes|yields?|yield)\b\s*:?\s*(?:about\s+)?"
                      r"(?P<n>\d+)(?:\s*(?:-|–|to)\s*(?P<n2>\d+))?\s*(?P<what>servings?|people|portions?|bowls?)?",
                      re.I)
SERVINGS_AFTER = re.compile(r"\b(?P<n>\d+)(?:\s*(?:-|–|to)\s*(?P<n2>\d+))?\s+(?:servings|portions)\b", re.I)


@dataclass
class Vocab:
    units: list            # (alias_lower, slug, kind) longest first
    terms: list            # (term_lower, ingredient slug) longest first
    unit_kind: dict = field(default_factory=dict)


def load_vocab(units_csv=HERE / "units.csv", seed_csv=HERE / "ingredients_seed.csv") -> Vocab:
    units, kinds = [], {}
    with open(units_csv, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            kinds[r["slug"]] = r["kind"]
            for a in {r["slug"], r["name"], r["plural"], *r["aliases"].split("|")}:
                a = a.strip().lower()
                if a:
                    units.append((a, r["slug"], r["kind"]))
    terms = []
    with open(seed_csv, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            for t in {r["name"], *r["aliases"].split("|")}:
                t = t.strip().lower()
                if t:
                    terms.append((t, r["slug"]))
    units.sort(key=lambda u: -len(u[0]))
    terms.sort(key=lambda t: -len(t[0]))
    return Vocab(units, terms, kinds)


def to_number(text: str) -> Fraction:
    text = text.strip()
    if " " in text:
        whole, frac = text.split(None, 1)
        return Fraction(whole) + Fraction(frac)
    return Fraction(text)


def normalise(text: str) -> str:
    for ch, rep in UNICODE_FRACTIONS.items():
        # "1½" -> "1 1/2", "½" -> "1/2"
        text = re.sub(rf"(\d){ch}", rf"\1 {rep}", text).replace(ch, rep)
    text = text.replace("⁄", "/").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_line(raw: str, vocab: Vocab) -> dict:
    text = normalise(BULLET.sub("", raw))
    out = {"raw_text": raw.strip(), "quantity": None, "quantity_max": None, "unit": None,
           "modifier": "", "ingredient": None, "preparation_note": None,
           "is_optional": False, "is_scalable": True, "package_grams": None,
           "package_ml": None, "match_term": None}
    rest = text
    low = rest.lower()
    if re.search(r"\boptional\b", low):
        out["is_optional"] = True

    m = QTY.match(rest)
    if m:
        out["quantity"] = to_number(m["q"])
        if m["q2"]:
            out["quantity_max"] = to_number(m["q2"])
        rest = rest[m.end():]
    else:
        for word in sorted(WORD_QUANTITIES, key=len, reverse=True):
            if re.match(rf"^{word}\b\s+", rest, re.I):
                out["quantity"] = Fraction(WORD_QUANTITIES[word])
                rest = rest[len(word):].lstrip()
                break

    # "1 (15 oz) can black beans": the package size gives the weight directly
    p = PAREN_SIZE.match(rest)
    if p and out["quantity"] is not None:
        n, u = to_number(p["n"]), p["u"].lower().replace(".", "").replace(" ", "")
        if u in ("oz", "ounce", "ounces"):
            out["package_grams"] = n * Fraction("28.3495")
        elif u in ("lb", "lbs"):
            out["package_grams"] = n * Fraction("453.592")
        elif u.startswith("g"):
            out["package_grams"] = n
        elif u == "ml":
            out["package_ml"] = n
        elif u == "floz":
            out["package_ml"] = n * Fraction("29.5735")
        rest = rest[p.end():]

    # Unit: only right after a quantity (or for subjective units anywhere),
    # so "l" in "lemon" or "c." in prose is never read as a unit.
    low = rest.lower()
    if out["quantity"] is not None:
        for alias, slug, kind in vocab.units:
            if re.match(rf"^{re.escape(alias)}(?![a-z])", low):
                if alias in ("l", "c.", "c") and not re.match(rf"^{re.escape(alias)}\s", low):
                    continue
                out["unit"] = slug
                rest = rest[len(alias):].lstrip(" .")
                break
    if out["unit"] is None:
        for alias, slug, kind in vocab.units:
            if kind == "subjective" and re.search(rf"\b{re.escape(alias)}\b", low):
                out["unit"], out["is_scalable"] = slug, False
                if alias in ("pinch", "pinches", "dash", "dashes", "splash", "drizzle"):
                    out["quantity"] = out["quantity"] or Fraction(1)
                break
    if out["unit"] in CONTAINERS and out["package_grams"] is None and out["package_ml"] is None:
        pass  # a can with no size: grams need an ingredient portion for 'can'

    low = rest.lower()
    for size in SIZES:
        if re.search(rf"\b{size}\b", low):
            out["modifier"] = size.replace("-", " ")
            break
    if out["unit"] in ("cup", "tbsp", "tsp") and not out["modifier"]:
        for prep in PREP_FOR_VOLUME:
            if re.search(rf"\b{prep}\b", low):
                out["modifier"] = prep
                break

    # Preparation note: after the first comma, or in trailing parentheses.
    name_part = rest
    if "," in rest:
        name_part, note = rest.split(",", 1)
        out["preparation_note"] = note.strip() or None
    name_part = re.sub(r"\([^)]*\)", " ", name_part)

    for term, slug in vocab.terms:
        if re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", name_part.lower()):
            out["ingredient"], out["match_term"] = slug, term
            break
    if out["ingredient"] is None:
        # The match might sit in the note ("1 cup chicken, cooked and shredded")
        for term, slug in vocab.terms:
            if re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", rest.lower()):
                out["ingredient"], out["match_term"] = slug, term
                break
    return out


def looks_like_ingredient(line: str, vocab: Vocab) -> bool:
    t = normalise(BULLET.sub("", line))
    if QTY.match(t):
        return True
    low = t.lower()
    return any(re.search(rf"\b{re.escape(a)}\b", low) for a, _, k in vocab.units if k == "subjective")


def find_servings(text: str):
    for rx in (SERVINGS, SERVINGS_AFTER):
        m = rx.search(text)
        if m:
            return int(m["n"]), m.group(0).strip()
    return None, None


def ingredient_block(text: str, vocab: Vocab) -> list[tuple[str, str | None]]:
    """(line, group_label) for the ingredient section of a description."""
    lines = [l.rstrip() for l in text.splitlines()]
    start = next((i + 1 for i, l in enumerate(lines) if HEADING.match(l)), None)
    if start is None:
        # No heading: the first run of 3+ ingredient-looking lines.
        run = []
        for i, l in enumerate(lines):
            if l.strip() and looks_like_ingredient(l, vocab):
                run.append(i)
                if len(run) >= 3:
                    start = run[0]
                    break
            elif l.strip():
                run = []
        if start is None:
            return []
    out, group, blanks = [], None, 0
    for l in lines[start:]:
        if not l.strip():
            blanks += 1
            if blanks >= 2 and out:
                break
            continue
        blanks = 0
        if STOP.match(l) or re.search(r"https?://", l):
            if out:
                break
            continue
        if not looks_like_ingredient(l, vocab) and GROUP.match(l) and len(l) < 40:
            group = l.strip().rstrip(":")
            continue
        if looks_like_ingredient(l, vocab) or len(l.split()) <= 6:
            out.append((l, group))
        elif out:
            break
    return out


def parse_description(text: str, vocab: Vocab) -> dict:
    servings, evidence = find_servings(text or "")
    lines = []
    for raw, group in ingredient_block(text or "", vocab):
        parsed = parse_line(raw, vocab)
        parsed["group_label"] = group
        lines.append(parsed)
    return {"servings": servings, "servings_evidence": evidence, "lines": lines}
