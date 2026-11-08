import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from measures import GramsError, load_units, parse_usda_portion, resolve_grams, to_fraction  # noqa

U = load_units()


@pytest.mark.parametrize("modifier,expected", [
    ("cup, fluid (yields 2 cups whipped)", ("cup", "fluid (yields 2 cups whipped)")),
    ("cup, whipped", ("cup", "whipped")),
    ("thigh with skin", ("thigh", "with skin")),
    ("tbsp, ground", ("tbsp", "ground")),
    ("tablespoon", ("tbsp", "")),
    ("fl oz", ("fl oz", "")),
    ("cloves", ("clove", "")),
    ('pat (1" sq, 1/3" high)', ("pat", '(1" sq, 1/3" high)')),
    ("cup shells", ("cup", "shells")),
])
def test_usda_portion_keeps_qualifier(modifier, expected):
    unit, qualifier, _ = parse_usda_portion(1, "", modifier, U)
    assert (unit, qualifier) == expected


@pytest.mark.parametrize("modifier", ["oz", "RACC", "cubic inch", ""])
def test_usda_portion_skips_mass_and_unknown(modifier):
    assert parse_usda_portion(1, "", modifier, U) is None


def test_fractions():
    assert to_fraction("1/2") == Fraction(1, 2)
    assert to_fraction("1 1/2") == Fraction(3, 2)
    assert to_fraction(0.25) == Fraction(1, 4)


CREAM = [{"unit": "cup", "qualifier": "whipped", "grams_per_unit": Fraction(120), "key": 1},
         {"unit": "cup", "qualifier": "fluid (yields 2 cups whipped)",
          "grams_per_unit": Fraction(238), "key": 2},
         {"unit": "tbsp", "qualifier": "", "grams_per_unit": Fraction(15), "key": 3}]


def test_cream_cup_needs_qualifier():
    # the bug the old pipeline shipped: plain "cup" silently took the whipped weight
    with pytest.raises(GramsError):
        resolve_grams(2, "cup", None, CREAM, U)
    assert resolve_grams(2, "cup", "fluid", CREAM, U)[:2] == (476, "portion")


def test_mass_and_volume_scaling():
    assert resolve_grams(1, "lb", None, [], U)[0] == Fraction("453.59237")
    grams, method, key = resolve_grams("1/2", "tsp", None, CREAM, U)
    assert method == "volume_scaled" and key == 3
    assert abs(float(grams) - 2.5) < 0.01          # 15 g per tbsp, 3 tsp per tbsp


def test_unknown_is_an_error_not_zero():
    with pytest.raises(GramsError):
        resolve_grams(1, "sprig", None, CREAM, U)
    assert resolve_grams(None, None, None, CREAM, U) == (None, None, None)
