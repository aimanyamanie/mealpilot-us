# 2026-10-29: YouTube description pipeline, test only

## Decision (Aiman)
Build the same pipeline as the Indonesian version: YouTube Data API, then video
descriptions, then parsed ingredient lines, then grams and nutrition. Use it for
**internal testing only**, while creator licences are pursued. This knowingly
departs from the sourcing rule in `2026-10-29-recipe-sourcing.md`: YouTube's
Developer Policies limit stored API data to 30 days and forbid deriving data from
it. The guardrails below keep it contained.

## Guardrails
- **Separate branch.** Everything goes to the Neon branch `dev-youtube-test`,
  created from `main` on 2026-10-29. `youtube_test.connect()` refuses to connect
  unless `.env.test` names that branch and its URL differs from `main`'s. Tests
  in `tests/test_youtube_guard.py` cover this.
- **30-day limit.** Raw responses go to `pipeline/data/youtube/` (gitignored),
  each stamped with `fetched_at`. `purge_youtube.py` deletes raw files and
  test-branch recipes older than 30 days.
- **Never published.** Creators are written with `permission_status = 'none'`,
  so `v_published_recipes` stays empty even on the test branch. Every recipe also
  carries the hold reasons `no_licence` and `nutrition_unreviewed`.
- **No copying to `main`.** A recipe reaches `main` only after it has been
  sourced again under a licence, or written up by hand.
- **Captions are never fetched**, and `search.list` is never used.

## What was built
- `fetch_youtube.py`: resolves each handle in `test_channels.csv`, then fetches
  the latest N uploads (default 50).
- `parse_recipe.py`: English ingredient-line parser with these features:
  - quantities: fractions, unicode ½, ranges, words like "a" and "one";
  - package sizes: "1 (15 oz) can";
  - units from `units.csv`, plus size and prep modifiers;
  - ingredients matched longest-first against `ingredients_seed.csv` aliases;
  - finding the ingredient block, group labels and servings.

  Golden cases are in `tests/golden_lines.json`.
- `load_recipes.py`: works out grams in the CLAUDE.md lookup order, nutrition per
  serving with exact fractions, coverage, the share of unverified ingredients, and
  hold reasons. It prints match and coverage rates and the top unmatched lines for
  each channel.

**Loader rules first set here:**
- A range ("2-3 cloves") uses the lower bound.
- When a nutrient is missing from the ingredient table, it's ignored if those lines
  are under 1% of the recipe's grams; otherwise the value is NULL and the recipe is
  held.
- No stated servings means `source_servings = 1` with confidence `guess`, and the
  recipe is held as `servings_unknown`.

## A bug the self-test caught, now fixed in the seed
"1 cup heavy cream" came out at 120 g, the weight of *whipped* cream. The USDA
portion mapper dropped any qualifier it didn't recognise, so whichever measure
came first became the plain cup. Other cases with the same cause:
- walnuts "in shell" (28 g a cup);
- bread "crust not eaten";
- a "plum tomato" for a medium tomato;
- pasta "shells" as the default cup.

Qualifiers are now kept as modifiers. Inedible forms are excluded. Brown sugar
(packed) and dry pasta (penne) have explicit defaults. Portions went from 512 to
538, and the review workbook was regenerated as
`ingredient_review_2026-10-29-v2.xlsx`.

## Test channels (`test_channels.csv`)
These were picked for having inline ingredient lists in their descriptions:
- Sip and Feast
- Clean & Delicious
- Vegan Richa
- Laura in the Kitchen
- Brian Lagerstrom
- MyHealthyDish

Most large US creators link to their website instead of listing ingredients in
the description, so expect many videos to be skipped as not recipes.
