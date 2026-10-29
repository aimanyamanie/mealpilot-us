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
        if key in ("quantity", "quantity_max", "package_grams") and want is not None:
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


def test_description_without_a_recipe():
    parsed = parse_description("New video every Friday! Follow me on Instagram.", VOCAB)
    assert parsed["lines"] == [] and parsed["servings"] is None
