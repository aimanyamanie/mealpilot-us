"""Golden cases for the English ingredient parser. Each case is plain JSON so
a port in another language can reuse it. Add one for every bug found."""
import json
import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parse_recipe import load_vocab, parse_description, parse_line  # noqa: E402

CASES = json.loads((Path(__file__).parent / "golden_lines.json").read_text(encoding="utf-8"))
VOCAB = load_vocab()


@pytest.mark.parametrize("case", CASES, ids=[c["line"] for c in CASES])
def test_golden_line(case):
    got = parse_line(case["line"], VOCAB)
    for key, want in case.items():
        if key == "line":
            continue
        if key in ("quantity", "quantity_max", "package_grams", "stated_grams") and want is not None:
            assert got[key] == Fraction(want), key
        else:
            assert got[key] == want, key


DESCRIPTION = """This creamy Tuscan chicken is our favorite weeknight dinner!

Serves 4

INGREDIENTS
1 1/2 lbs boneless skinless chicken thighs
1 tsp kosher salt
2 tbsp olive oil
For the sauce:
3 cloves garlic, minced
1 cup heavy cream
1/2 cup grated parmesan
2 cups baby spinach

INSTRUCTIONS
1. Season the chicken...

Get the full recipe: https://example.com/tuscan-chicken
0:00 Intro
"""


def test_description_block_servings_and_groups():
    parsed = parse_description(DESCRIPTION, VOCAB)
    assert parsed["servings"] == 4
    slugs = [l["ingredient"] for l in parsed["lines"]]
    assert slugs == ["chicken-thigh", "salt", "olive-oil", "garlic", "heavy-cream",
                     "parmesan", "spinach"]
    assert parsed["lines"][3]["group_label"] == "For the sauce"
    assert parsed["lines"][0]["group_label"] is None


CREDITS_AND_SECTIONS = """Ingredients
--
1 lb ground beef
Dressing:
2 tbsp olive oil
1 tbsp red wine vinegar
Toppings
Fresh basil

Video editor: Billy Mark: @bluecrestproductions
Disclosure: this video contains affiliate links
"""


def test_sections_separators_and_credits():
    parsed = parse_description(CREDITS_AND_SECTIONS, VOCAB)
    got = [(l["ingredient"], l["group_label"]) for l in parsed["lines"]]
    assert got == [("beef-ground-85", None), ("olive-oil", "Dressing"),
                   ("vinegar-red-wine", "Dressing"), ("basil", "Toppings")]


def test_numbered_steps_end_the_ingredient_list():
    text = ("Ingredients\n1 lb spaghetti\n2 tbsp olive oil\n\n"
            "6 While the sauce reduces, cook your spaghetti in boiling water 10-12 minutes.\n")
    parsed = parse_description(text, VOCAB)
    assert [l["ingredient"] for l in parsed["lines"]] == ["pasta-dry", "olive-oil"]


@pytest.mark.parametrize("text, servings", [
    ("Serves 4", 4),
    ("Makes 6 servings", 6),
    ("Yield: 8", 8),
    ("This makes 4-6 servings", 4),
    ("Pour into bowl (yields about 115g). Chill 15 mins", None),   # a weight, not servings
    ("Makes 2 cups of sauce", None),
])
def test_servings(text, servings):
    from parse_recipe import find_servings
    assert find_servings(text)[0] == servings


def test_description_without_a_recipe():
    parsed = parse_description("New video every Friday! Follow me on Instagram.", VOCAB)
    assert parsed["lines"] == [] and parsed["servings"] is None
