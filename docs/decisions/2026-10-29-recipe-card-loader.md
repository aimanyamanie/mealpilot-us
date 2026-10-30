# 2026-10-29: Recipe-card loader and creator permissions register

## Why
This is the licensed path from `2026-10-29-recipe-sourcing.md`. YouTube descriptions
rarely state servings: 16 of 159 test recipes did, and 0 of 93 for Joshua Weissman.
Large creators keep their recipes on their own sites. A creator's recipe card
(schema.org `Recipe` JSON-LD) almost always states servings, times and category.

## What was built
- `parse_card.py`: reads one schema.org Recipe into our fields:
  - servings from `recipeYield` ("4", ["4","4 servings"], "Serves 4", "12 cookies");
  - prep and cook minutes from ISO durations;
  - steps flattened from HowToSection, HowToStep or plain strings;
  - `recipeCategory` mapped to recipe type and meal slots (Main Course becomes lunch
    and dinner, Breakfast becomes breakfast, Dessert is not plannable);
  - cuisine, page URL and image;
  - the YouTube video id (embed, watch or nocookie URLs);
  - the card's own calories, kept as a cross-check only.
- `fetch_card.py`: saves the card from one page, or from a page file the creator
  sends. It **refuses unless the creator has granted `recipe_data`**, and reads one
  page per call: a licence to use recipes is not a licence to crawl.
- `load_cards.py`: writes to `main` for licensed creators. With `--test` it writes
  our own sample cards to `dev-youtube-test`. Every recipe is saved `in_review`
  with its hold reasons:
  - servings unknown, coverage under 90%, a missing nutrient;
  - **the card's calories differing from ours by more than 25%**;
  - steps not rewritten, unknown category, no video;
  - meal-prep fields missing, nutrition unreviewed.
- `recipe_store.py`: the grams and nutrition rules, moved out of `load_recipes.py` so
  both loaders apply exactly the same maths. The YouTube results were identical
  after the move.
- `permissions.csv` + `permissions.py`: the register of creator approvals.
  - **Granted** needs a date, `recipe_data` in scope, an evidence file in
    `permissions/evidence/` (gitignored), and who obtained it.
  - `python permissions.py` checks the register and syncs each creator's
    permission status to `main`.

## A rule found while testing: drained cans
"2 (15 oz) cans chickpeas, drained" was counted at 850 g, the can's net weight with
its liquid. USDA's drained can is about 253 g, and the nutrition record is for the
drained food. When the line says "drained" and the ingredient has a can portion,
the loader now uses the drained weight. The sample salad went from 329 to
249 kcal a serving. That card's 250 kcal is my own sample figure, so this is a
sanity check, not validation.

## Sample run (my own four cards, test branch)
- Lemon garlic chicken: serves 4, 100% coverage, 348 kcal.
- Chickpea salad: serves 6, 100% coverage, 249 kcal.
- Shrimp stir fry: from an HTML page with an `@graph`. Serves 4, 100% coverage, but
  **held**, because USDA publishes no sugar or fiber for shrimp.
- Overnight oats: serves 2, 67% coverage. **Held**: Greek yogurt and chia seeds have
  no cup or tablespoon weight in USDA.

None was published: no licence, steps not rewritten, nutrition not reviewed.

## Also learned: how far back to fetch on YouTube
Joshua Weissman's latest 50 uploads gave 0 recipes. His full catalogue of 836
uploads gave 93, all from 2017–2022: he stopped putting ingredients in
descriptions in 2023. Older uploads matter for description parsing.

## Added later the same day
- **Frying oil** (`recipe_store.is_frying_oil`): an oil line that says "for frying"
  or "deep fry", or is a cup or more, or is measured in quarts or liters.
  - It stays on the shopping list, but its calories are not counted.
  - It doesn't count against coverage.
  - The recipe is held with `frying_oil_absorption_unknown`.

  Only part of frying oil ends up in the food, and no single authoritative factor
  covers every fried food. Choosing one is a decision; it's listed as open in
  CLAUDE.md. Before this rule, Joshua Weissman's katsu counted all 2 cups.
- **Storage defaults** (`recipe_store.storage_defaults`): from USDA FSIS,
  "Leftovers and Food Safety":
  - 3 days in the fridge (the low end of FSIS's 3–4);
  - 90 days in the freezer (low end of 3–4 months), or none for salads,
    sandwiches, smoothies and overnight oats;
  - reheat to 165 °F.

  `storage_source` says it's a default. Every recipe stays held as
  `storage_default_unreviewed` until someone decides who sets storage per recipe.

## Not yet
- Steps in our own words.
- Portion description in household measures.
- Cost per serving.
- Refreshing the 30-day YouTube metadata.
