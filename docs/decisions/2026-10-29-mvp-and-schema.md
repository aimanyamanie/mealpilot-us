# 2026-10-29: MVP scope, stack and the US schema

## Decided with Aiman
- **Recipes:** US YouTube creators, parsed from video descriptions, with links back to and embeds of the videos.
- **Platform:** a mobile-friendly web app.
- **MVP:** onboarding gives a calorie target, which drives a 30-day plan with diet and allergen filters and a weekly grocery list.
- **Stack:**
  - Python data pipeline in `pipeline/`, run offline.
  - Postgres on Neon, US East.
  - Next.js + TypeScript web app in `web/`, reading the database only through the views in `pipeline/views.sql`.
- **Reuse from the Indonesian repo:**
  - Port the planner (`meal_planner.py`) to TypeScript.
  - Port the nutrition engine, simplified.
  - Redesign the schema in English.
  - Rewrite the ingredient parser.
  - Steps (method text) come after the MVP; the video is the method until then.

The full milestone plan, M0 to M5, was approved in this session. Its lasting parts are recorded here.

## How the schema differs from the Indonesian one

1. **`ingredient_portions` is new.** US recipes measure by volume and by the piece. One
   `density_g_per_ml` and one `grams_per_piece` per ingredient can't represent
   "1 cup chopped onion" vs "1 cup minced", or "1 medium" vs "1 large" onion. USDA
   FoodData Central publishes exactly these as `foodPortions`, so each portion row cites
   one. The order for working out grams on a line:
   1. a mass unit;
   2. an exact `(ingredient, unit, modifier)` portion;
   3. that unit's default portion;
   4. density, for volume;
   5. otherwise NULL, which counts against coverage.
2. **Allergens are typed columns, not a pipe-separated flag string.** There's one
   boolean per FDA major allergen, plus `has_gluten`, which isn't the same as wheat.
   `allergens_reviewed` exists because an unreviewed ingredient must make a recipe
   "unknown", never "free". `v_recipe_flags.flags_known` carries that through.
3. **Diet comes from `animal_source`**, not from flags. Vegetarian and vegan are both
   derived from it, so they can't contradict each other.
4. **Creator permission is a column.** `v_published_recipes` requires
   `permission_status = 'granted'`, so publishing without permission is impossible,
   not just discouraged.
5. **Every column is in `schema.sql`.** The old loader added columns at runtime with
   `ALTER TABLE`, and the schema file drifted from the database.
6. **Dropped:** Indonesian names (`*_id` columns), `plate_role`, TKPI/MEXT/KFCT sources
   and the pork regex view. `steps` is left out until after the MVP.
7. **Shopping columns** (`store_section`, `shop_unit`, `shop_unit_grams`) are new. The
   old grocery list only counted meals, and the US one has to say "2 lb" or "1 can".

## Units
`pipeline/units.csv` uses US customary factors: cup = 236.588 ml, not 240. Size words
(small/medium/large) are modifiers that match `ingredient_portions`, not units.
`T` and `t` (tablespoon and teaspoon) are deliberately not aliases, because matching
is case-insensitive. The parser has to handle them case-sensitively, or leave them for
review.

## Verified so far
- `pytest pipeline/tests`: the units.csv structure, unique aliases, and US factor
  relationships.
- `schema.sql` and `views.sql` parse with the Postgres parser (pglast). They haven't
  been applied to a real database yet. That happens once the Neon project exists.
