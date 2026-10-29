"""Seed checks: the committed CSVs pass validation, and USDA portion text maps
to the right unit, modifier and grams. Each portion case is a real USDA
measure string."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_seed import map_portion  # noqa: E402
from validate_seed import check, read  # noqa: E402


def test_committed_seed_has_no_errors():
    errors, _ = check(read("ingredients_seed.csv"),
                      read("ingredient_portions_seed.csv"), read("units.csv"))
    assert errors == []


def p(amount, modifier, grams, unit=""):
    return {"amount": amount, "unit": unit, "modifier": modifier, "grams": grams}


@pytest.mark.parametrize("portion, expected", [
    (p(1, "cup, chopped", 160), ("cup", "chopped", 160)),
    (p(1, 'medium (2-1/2" dia)', 110), ("piece", "medium", 110)),
    (p(1, "large", 50), ("piece", "large", 50)),
    (p(1, "extra large", 56), ("piece", "extra large", 56)),
    (p(3, "cloves", 9), ("clove", "", 3)),               # per ONE unit
    (p(1, "tbsp chopped", 10), ("tbsp", "chopped", 10)),
    (p(1, 'slice, medium (1/8" thick)', 14), ("slice", "medium", 14)),
    (p(1, "almond", 1.2), ("piece", "", 1.2)),           # the measure names the food
    (p(1, "Edible", 143, unit="Onion"), ("piece", "", 143)),
    # A qualifier is kept, so it cannot become the plain measure:
    (p(1, "cup, whipped", 120), ("cup", "whipped", 120)),
    (p(1, "cup, fluid (yields 2 cups whipped)", 238), ("cup", "", 238)),
    (p(1, "cup, cubes", 140), ("cup", "cubed", 140)),
    (p(1, "plum tomato", 62), ("piece", "plum tomato", 62)),
    (p(1, "can (12.5 oz), drained", 315), ("can", "12.5 oz", 315)),
    (p(1, "cup shelled (50 halves)", 100), ("cup", "", 100)),
])
def test_portion_mapping(portion, expected):
    unit, modifier, grams = map_portion(portion)
    assert (unit, modifier) == expected[:2]
    assert grams == pytest.approx(expected[2])


@pytest.mark.parametrize("portion", [
    p(4, "oz", 113),                  # mass: the units table already covers it
    p(1, "package", 926),             # not a household measure
    p(10, "rings", 60),
    p(1, "serving packet", 2.8),
    p(1, "", 30, unit="RACC"),
    p(1, "cup, in shell, edible yield (7 nuts)", 28),   # not the food a recipe means
    p(1, "slice crust not eaten", 12),
])
def test_portions_that_are_skipped(portion):
    assert map_portion(portion) is None
