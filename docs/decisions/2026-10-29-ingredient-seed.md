# 2026-10-29: First US ingredient seed from USDA FoodData Central

## What was built
- **225 ingredients** (`pipeline/ingredients_seed.csv`) and **512 household portions**
  (`pipeline/ingredient_portions_seed.csv`), loaded into Neon `mealpilot-us`.
- **The source is the USDA bulk downloads, not the API:** Foundation Foods
  2026-10 and SR Legacy 2018-04, both public domain. They're stored in
  `pipeline/data/usda/`, which is gitignored and can be downloaded again. No FDC
  API key is needed.
- **How it fits together:**
  - `ingredient_list.csv` says what each ingredient is: name, aliases, category,
    store section, allergens, animal source.
  - `usda_picks.csv` says which USDA record it was matched to, with a note
    wherever the obvious record wasn't used.
  - `build_seed.py` joins the two.
  - `validate_seed.py` checks them, and `load_seed.py` loads them.

## How records were picked
`usda.py candidates` lists the top matches for each ingredient. Each pick was then
made by reading the description, not by taking the top hit:
- **Foundation Foods** (the newer analyses) is used for nutrition when its record is
  complete.
- **SR Legacy** is used otherwise. Examples: Foundation records with no energy value
  (shallot, salted butter, canola oil, raisins), Foundation's negative carbohydrate
  for ground lamb, and cases where Foundation only has a narrower food (spaghetti
  rather than dry pasta, named apple varieties, bananas split by ripeness).
- **Portions** (cup, tbsp, "1 medium", "1 clove") come from the SR Legacy twin,
  because Foundation publishes few household measures.
- **Missing fiber, sugar or sodium** on a Foundation record is taken from that twin,
  and the ingredient's `notes` say which nutrient came from where.
- **Default portion size** is medium, except eggs: US recipes assume large eggs.

## Status of every row
- `data_quality = verified` for 221 rows: the record was chosen by reading its
  description, and its id is in `source_ref`. `verified_by` says this was Claude.
- `data_quality = researched` for 4 rows that stand in for foods USDA doesn't
  publish: Dijon mustard (uses yellow), rice vinegar (uses distilled), chocolate
  chips (uses 45–59% dark), panko (uses dry breadcrumbs).
- **All 225 rows are `needs_verification = true` and `allergens_reviewed = false`.**
  A human must sign off both. Until then `v_recipe_flags.flags_known` stays false,
  so no recipe is shown as allergen-free.

## Gaps a human should fill
- **USDA doesn't publish sugar** for 21 rows: herbs, shrimp, tofu, tempeh, quinoa,
  couscous, almond flour, chia, pinto beans, avocado oil, coconut milk, beef broth,
  some dried spices, frozen mixed vegetables. **Fiber is missing** for 5: shrimp,
  tempeh, pinto beans, coconut milk, balsamic vinegar. They're left NULL rather than
  guessed. How the recipe loader treats a NULL nutrient on a minor ingredient is a
  decision for the loader (M2).
- **No household portions** for 18 rows:
  - Ground meats, chuck and lamb are fine, since they're bought and measured by
    weight.
  - Rows that still need a measured or label portion: shrimp (count), Greek yogurt,
    goat cheese, rice noodles, almond flour, cashews, chia seeds, marinara,
    chocolate chips, white and red wine. Without one, a cup or piece line for these
    can't be converted to grams, and it counts against coverage.
- **Can and package weights** (a 15 oz can of beans, drained) aren't in USDA. They
  belong with the shopping units and prices, which are still open in CLAUDE.md.

## Checks
- `validate_seed.py`: 0 errors. It checks alias collisions, allergen consistency
  (dairy without milk, wheat without gluten), protein below 12 g for meat, and one
  default per unit.
- 28 warnings. Most are USDA not publishing a nutrient. Two are Atwater gaps that
  are real data: cocoa powder (228 kcal vs 359 by 4/4/9) and dried dill.
- `pytest pipeline/tests`: 19 passed, including real USDA portion strings mapped
  to unit, modifier and grams.
- Loading twice gives the same counts: units and ingredients are upserted by slug,
  and portions are replaced.
