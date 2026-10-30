"""Grams and nutrition rules in recipe_store.py, on a small in-memory
reference (no database)."""
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parse_recipe import load_vocab, parse_line  # noqa: E402
from recipe_store import grams_for, nutrition, prepare_lines, storage_defaults  # noqa: E402

F = Fraction
UNITS = {"g": (1, "mass", F(1)), "lb": (2, "mass", F("453.592")), "cup": (3, "volume", F("236.588")),
         "can": (4, "count", None), "piece": (5, "count", None), "to-taste": (6, "subjective", None),
         "tbsp": (7, "volume", F("14.7868")), "quart": (8, "volume", F("946.353"))}


def ing(kcal, sugar=F(0), density=None, category="other"):
    return {"id": 1, "kcal": F(kcal), "protein": F(0), "carb": F(0), "fat": F(0), "fiber": F(0),
            "sugar": sugar, "sodium_mg": F(0), "density": density, "edible_pct": F(100), "unverified": True,
            "category": category}


INGREDIENTS = {"chickpeas-canned": ing(139), "olive-oil": ing(884, density=F("0.913"), category="oil"),
               "vegetable-oil": ing(884, density=F("0.92"), category="oil"),
               "salt": ing(0), "shrimp": ing(76, sugar=None), "garlic": ing(143)}
PORTIONS = {("chickpeas-canned", "can", ""): F(253), ("garlic", "clove", ""): F(3)}
DEFAULTS = {("chickpeas-canned", "can"): F(253)}
REF = (UNITS, INGREDIENTS, PORTIONS, DEFAULTS)
VOCAB = load_vocab()


def line(text, **over):
    parsed = parse_line(text, VOCAB)
    parsed.update(over)
    return parsed


def test_drained_can_uses_drained_weight():
    l = line("2 (15 oz) cans chickpeas, drained and rinsed", ingredient="chickpeas-canned")
    assert grams_for(l, REF) == (F(506), "portion")


def test_undrained_can_uses_package_weight():
    l = line("1 (15 oz) can chickpeas", ingredient="chickpeas-canned")
    grams, how = grams_for(l, REF)
    assert how == "mass" and round(float(grams)) == 425


def test_stated_grams_win():
    l = line("1/2 cup (45g) olive oil", ingredient="olive-oil")
    assert grams_for(l, REF) == (F(45), "mass")


def test_volume_uses_density_when_no_portion():
    l = line("2 tbsp olive oil", ingredient="olive-oil")
    grams, how = grams_for(l, REF)
    assert how == "density" and round(float(grams), 1) == 27.0


def test_to_taste_does_not_count_against_coverage():
    lines = prepare_lines([line("1 lb chickpeas", ingredient="chickpeas-canned"),
                           line("salt to taste", ingredient="salt")], REF)
    result = nutrition(lines, INGREDIENTS, F(4))
    assert result["coverage"] == 1


def test_missing_nutrient_on_a_big_line_holds_the_recipe():
    lines = prepare_lines([line("1 lb shrimp", ingredient="shrimp")], REF)
    result = nutrition(lines, INGREDIENTS, F(4))
    assert result["per_serving"]["sugar"] is None and "no_sugar" in result["held"]


def test_missing_nutrient_on_a_tiny_line_is_ignored():
    lines = prepare_lines([line("1 lb chickpeas", ingredient="chickpeas-canned"),
                           line("1 g shrimp", ingredient="shrimp")], REF)
    result = nutrition(lines, INGREDIENTS, F(1))
    assert result["per_serving"]["sugar"] == 0 and result["held"] == []


import pytest  # noqa: E402


@pytest.mark.parametrize("text, frying", [
    ("2 cups oil", True),                              # Joshua Weissman's katsu
    ("vegetable oil, for frying", True),
    ("1 quart vegetable oil, for deep frying", True),
    ("2 tbsp olive oil", False),
    ("1/4 cup extra virgin olive oil", False),
])
def test_frying_oil(text, frying):
    lines = prepare_lines([line(text)], REF)
    assert lines[0]["frying_oil"] is frying
    if frying:
        assert lines[0]["grams_edible"] is None and not lines[0]["counts_for_coverage"]


def test_frying_oil_holds_the_recipe_but_not_coverage():
    lines = prepare_lines([line("1 lb chickpeas", ingredient="chickpeas-canned"), line("2 cups oil")], REF)
    result = nutrition(lines, INGREDIENTS, F(4))
    assert result["coverage"] == 1 and "frying_oil_absorption_unknown" in result["held"]
    assert result["per_serving"]["kcal"] == F(453592, 1000) * 139 / 100 / 4   # the oil adds nothing


def test_storage_defaults():
    assert storage_defaults("Beef Chili", "meal")["freezer_days"] == 90
    assert storage_defaults("Chickpea Cucumber Salad", "meal")["freezer_days"] is None
    assert storage_defaults("Lemonade", "drink") == {}


def test_garlic_cloves_without_a_unit():
    l = line("2 garlic cloves, minced", ingredient="garlic")
    assert l["unit"] is None
    assert grams_for(l, (UNITS, INGREDIENTS, PORTIONS, {**DEFAULTS, ("garlic", "clove"): F(3)})) == (F(6), "portion")
