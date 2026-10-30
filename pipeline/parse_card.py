"""schema.org Recipe (a creator's recipe card) -> our recipe fields.

Creators' sites publish their recipe cards as JSON-LD, usually written by
WP Recipe Maker or Tasty Recipes. This reads one card into the fields
load_cards.py saves. Pure functions, no database or network.

    find_recipe(json_ld) -> the Recipe object inside a JSON-LD blob
    parse_card(recipe, vocab) -> {"title", "servings", "lines", "steps", ...}

The card is only read under a creator's licence (permissions.csv).
"""
import json
import re
from html import unescape

from parse_recipe import Vocab, find_servings, parse_line

ISO_DURATION = re.compile(r"^P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$")
YOUTUBE_ID = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=|shorts/)|youtu\.be/)([\w-]{11})")
# recipeCategory -> (recipe_type, meal slots). Unknown categories leave both empty for review.
CATEGORIES = {
    "breakfast": ("meal", ["breakfast"]), "brunch": ("meal", ["breakfast"]),
    "lunch": ("meal", ["lunch"]), "dinner": ("meal", ["dinner"]),
    "main course": ("meal", ["lunch", "dinner"]), "main dish": ("meal", ["lunch", "dinner"]),
    "entree": ("meal", ["lunch", "dinner"]), "main": ("meal", ["lunch", "dinner"]),
    "soup": ("meal", ["lunch", "dinner"]), "salad": ("meal", ["lunch", "dinner"]),
    "side dish": ("side", None), "side": ("side", None),
    "snack": ("snack", ["snack"]), "appetizer": ("snack", ["snack"]),
    "dessert": ("dessert", None), "drinks": ("drink", None), "drink": ("drink", None),
    "beverage": ("drink", None), "sauce": ("component", None), "condiment": ("component", None),
}


def find_recipe(blob):
    """The first Recipe in a JSON-LD blob: a dict, a list, or an @graph."""
    if isinstance(blob, str):
        blob = json.loads(blob)
    if isinstance(blob, list):
        for item in blob:
            found = find_recipe(item)
            if found:
                return found
        return None
    if not isinstance(blob, dict):
        return None
    kind = blob.get("@type")
    if kind == "Recipe" or (isinstance(kind, list) and "Recipe" in kind):
        return blob
    if "@graph" in blob:
        return find_recipe(blob["@graph"])
    return None


def minutes(value):
    m = ISO_DURATION.match((value or "").strip())
    if not m or not any(m.groupdict().values()):
        return None
    d, h, mi, s = (int(x) if x else 0 for x in (m["d"], m["h"], m["m"], m["s"]))
    seconds = d * 86400 + h * 3600 + mi * 60 + s
    return int(seconds / 60 + 0.5)        # nearest minute, halves up


def clean(text):
    text = unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    return re.sub(r"\s+", " ", text).strip()


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def servings_from_yield(value):
    """recipeYield is "4", 4, ["4", "4 servings"], "Serves 4" or "12 cookies"."""
    for item in as_list(value):
        text = clean(item)
        if re.fullmatch(r"\d+", text):
            return int(text), f'recipeYield: "{text}"'
        n, evidence = find_servings(text)
        if n:
            return n, f'recipeYield: "{text}"'
        m = re.match(r"^(\d+)\s+([a-z]+)", text, re.I)   # "12 cookies", "8 bowls"
        if m:
            return int(m[1]), f'recipeYield: "{text}"'
    return None, None


def steps(instructions):
    """Flatten HowToStep / HowToSection / plain strings into step texts."""
    out = []
    for item in as_list(instructions):
        if isinstance(item, str):
            out += [s for s in (clean(x) for x in re.split(r"\n+", item)) if s]
        elif isinstance(item, dict):
            if item.get("@type") == "HowToSection" or "itemListElement" in item:
                out += steps(item.get("itemListElement"))
            else:
                text = clean(item.get("text") or item.get("name"))
                if text:
                    out.append(text)
    return out


def classify(categories):
    for c in as_list(categories):
        hit = CATEGORIES.get(clean(c).lower())
        if hit:
            return hit
    return None, None


def video_id(recipe):
    for video in as_list(recipe.get("video")):
        if isinstance(video, dict):
            for key in ("embedUrl", "contentUrl", "url"):
                m = YOUTUBE_ID.search(str(video.get(key) or ""))
                if m:
                    return m[1]
    return None


def page_url(recipe):
    page = recipe.get("mainEntityOfPage")
    if isinstance(page, dict):
        page = page.get("@id")
    return recipe.get("url") or page


def creator_kcal(recipe):
    n = recipe.get("nutrition") or {}
    m = re.search(r"[\d.]+", str(n.get("calories") or ""))
    return float(m.group(0)) if m else None


def parse_card(recipe: dict, vocab: Vocab) -> dict:
    servings, evidence = servings_from_yield(recipe.get("recipeYield"))
    recipe_type, slots = classify(recipe.get("recipeCategory"))
    image = as_list(recipe.get("image"))
    image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")
    lines = []
    for raw in as_list(recipe.get("recipeIngredient")):
        text = clean(raw)
        if text:
            parsed = parse_line(text, vocab)
            parsed["group_label"] = None      # JSON-LD flattens WPRM groups
            lines.append(parsed)
    return {
        "title": clean(recipe.get("name")),
        "servings": servings, "servings_evidence": evidence,
        "lines": lines, "steps": steps(recipe.get("recipeInstructions")),
        "prep_minutes": minutes(recipe.get("prepTime")),
        "cook_minutes": minutes(recipe.get("cookTime")),
        "total_minutes": minutes(recipe.get("totalTime")),
        "recipe_type": recipe_type, "meal_slots": slots,
        "cuisine": clean(as_list(recipe.get("recipeCuisine"))[0]) if recipe.get("recipeCuisine") else None,
        "video_id": video_id(recipe),
        "url": page_url(recipe),
        "image": image,
        "creator_kcal": creator_kcal(recipe),
        "published_on": (recipe.get("datePublished") or "")[:10] or None,
    }
