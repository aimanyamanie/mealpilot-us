import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from load_recipe import check_evidence  # noqa

SEGS = [{"text": "four cloves of garlic crushed and i am", "start": 166.2},
        {"text": "going to fine chop these", "start": 168.2},
        {"text": "next up fresh thyme right these are", "start": 208.6}]


def line(ev, t):
    return {"text": "x", "evidence": ev, "t": t}


def test_quote_across_segments_passes():
    assert check_evidence([line("crushed and i am going to fine chop", 166)], SEGS) == []


def test_invented_quote_fails():
    assert check_evidence([line("two cups of heavy cream", 166)], SEGS)


def test_quote_far_from_timestamp_fails():
    assert check_evidence([line("next up fresh thyme", 100)], SEGS)


def test_missing_evidence_fails():
    assert check_evidence([{"text": "x", "evidence": None, "t": 1}], SEGS)
