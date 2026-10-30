"""Recipe-card parsing on sample cards we wrote ourselves (tests/cards/),
in the shapes WP Recipe Maker and Tasty Recipes publish, plus the
permissions gate."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import permissions  # noqa: E402
from fetch_card import extract_recipe  # noqa: E402
from parse_card import find_recipe, minutes, parse_card, servings_from_yield  # noqa: E402
from parse_recipe import load_vocab  # noqa: E402

CARDS = Path(__file__).parent / "cards"
VOCAB = load_vocab()


def card(name):
    return parse_card(find_recipe(json.loads((CARDS / name).read_text(encoding="utf-8"))), VOCAB)


def test_full_card():
    c = card("lemon-garlic-chicken-thighs.json")
    assert c["title"] == "Lemon Garlic Chicken Thighs"
    assert (c["servings"], c["prep_minutes"], c["cook_minutes"]) == (4, 10, 25)
    assert (c["recipe_type"], c["meal_slots"], c["cuisine"]) == ("meal", ["lunch", "dinner"], "American")
    assert c["video_id"] == "AbCdEfGhIjK"
    assert c["creator_kcal"] == 315
    assert len(c["steps"]) == 4                      # two HowToSections flattened
    assert all(l["ingredient"] for l in c["lines"])  # every line matched


def test_plain_string_steps_and_yield():
    c = card("chickpea-cucumber-salad.json")
    assert c["servings"] == 6 and len(c["steps"]) == 3 and c["video_id"] is None
    chickpeas = c["lines"][0]
    assert chickpeas["ingredient"] == "chickpeas-canned" and chickpeas["package_grams"] is not None


def test_breakfast_category():
    c = card("overnight-oats.json")
    assert (c["servings"], c["recipe_type"], c["meal_slots"]) == (2, "meal", ["breakfast"])


def test_recipe_inside_a_page_graph():
    html = (CARDS / "shrimp-stir-fry-page.html").read_text(encoding="utf-8")
    recipe = extract_recipe(html)
    c = parse_card(recipe, VOCAB)
    assert c["title"] == "Garlic Shrimp Stir Fry"
    assert c["url"] == "https://example.com/garlic-shrimp-stir-fry/"
    assert c["video_id"] == "ZyXwVuTsRqP"            # youtube-nocookie embed


@pytest.mark.parametrize("value, n", [
    ("4", 4), (4, 4), (["4", "4 servings"], 4), ("Serves 6", 6), ("12 cookies", 12),
    ("8 bowls", 8), (None, None), ("", None),
])
def test_yield_shapes(value, n):
    assert servings_from_yield(value)[0] == n


@pytest.mark.parametrize("iso, mins", [("PT10M", 10), ("PT1H30M", 90), ("P0DT0H45M", 45),
                                       ("PT90S", 2), ("", None), ("PT", None)])
def test_durations(iso, mins):
    assert minutes(iso) == mins


def test_unlicensed_creator_is_refused():
    with pytest.raises(SystemExit):
        permissions.granted("sip-and-feast")         # status 'none' in the register


def test_register_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(permissions, "EVIDENCE", tmp_path)
    (tmp_path / "ok.png").write_bytes(b"x")
    rows = {
        "good": {"status": "granted", "date": "2026-11-03", "scope": "recipe_data|embed",
                 "evidence": "ok.png", "obtained_by": "Aiman"},
        "no-scope": {"status": "granted", "date": "2026-11-03", "scope": "embed",
                     "evidence": "ok.png", "obtained_by": "Aiman"},
        "no-evidence": {"status": "granted", "date": "2026-11-03", "scope": "recipe_data",
                        "evidence": "missing.png", "obtained_by": "Aiman"},
        "asked": {"status": "requested", "date": "", "scope": "", "evidence": "", "obtained_by": ""},
    }
    got = permissions.problems(rows)
    assert not [p for p in got if p.startswith("good:")]
    assert any(p.startswith("no-scope:") for p in got)
    assert any(p.startswith("no-evidence:") for p in got)
    assert not [p for p in got if p.startswith("asked:")]
