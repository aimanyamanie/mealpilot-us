"""Save a licensed creator's recipe card (schema.org JSON-LD) from its page.

    python fetch_card.py sip-and-feast https://www.sipandfeast.com/some-recipe/
    python fetch_card.py sip-and-feast page.html     # a page saved or exported by the creator

Refuses unless permissions.csv says the creator granted recipe_data.
Writes data/cards/<creator>/<page-slug>.json (gitignored), stamped with
the URL and fetch time. Reads one page per call, on purpose: a licence to
use recipes is not a licence to crawl a site.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from parse_card import find_recipe
from permissions import granted

HERE = Path(__file__).resolve().parent
CARDS = HERE / "data" / "cards"
USER_AGENT = "MealPilot recipe-card reader (licensed use; contact via MealPilot)"
JSON_LD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)


def extract_recipe(html: str):
    for block in JSON_LD.findall(html):
        try:
            recipe = find_recipe(json.loads(block.strip()))
        except json.JSONDecodeError:
            continue
        if recipe:
            return recipe
    return None


def page_slug(source: str) -> str:
    path = urlparse(source).path if source.startswith("http") else Path(source).stem
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    return slug.split("-", 1)[-1] if slug.startswith("html") else (slug or "recipe")


def main(argv) -> int:
    if len(argv) != 2:
        sys.exit(__doc__)
    creator, source = argv
    granted(creator)
    if source.startswith("http"):
        r = requests.get(source, headers={"User-Agent": USER_AGENT}, timeout=30)
        r.raise_for_status()
        html = r.text
    else:
        html = Path(source).read_text(encoding="utf-8")
    recipe = extract_recipe(html)
    if not recipe:
        print(f"No schema.org Recipe found in {source}")
        return 1
    out_dir = CARDS / creator
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{page_slug(source)}.json"
    out.write_text(json.dumps({"source": source,
                               "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "recipe": recipe}, indent=1), encoding="utf-8")
    print(f"{recipe.get('name')!r} -> {out.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
