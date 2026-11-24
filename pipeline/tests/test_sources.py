import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from load_recipe import amount_source, check_sources  # noqa

URL = "https://www.joshuaweissman.com/post/perfect-fettuccine-alfredo"


def line(basis, **kw):
    return {"text": "x", "basis": basis, **kw}


def test_defaults_follow_basis():
    assert amount_source(line("stated"))[0] == "transcript"
    assert amount_source(line("estimated"))[0] == "our_estimate"
    assert amount_source(line("to_taste"))[0] is None
    assert check_sources([line("stated"), line("estimated"), line("to_taste")]) == []


def test_creator_recipe_with_url_and_note_passes():
    ln = line("estimated", amount_source="creator_recipe", amount_url=URL, amount_note="scaled 8/7")
    assert check_sources([ln]) == []


def test_creator_recipe_needs_url_and_note():
    assert check_sources([line("estimated", amount_source="creator_recipe", amount_note="n")])
    assert check_sources([line("estimated", amount_source="creator_recipe", amount_url=URL)])


def test_url_only_with_creator_recipe():
    assert check_sources([line("estimated", amount_url=URL)])


def test_source_must_fit_basis():
    assert check_sources([line("stated", amount_source="our_estimate")])
    assert check_sources([line("estimated", amount_source="transcript")])
    assert check_sources([line("to_taste", amount_source="transcript")])
