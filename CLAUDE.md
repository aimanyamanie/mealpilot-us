# MealPilot US: recipe catalogue database

The **US market's recipe catalogue** for the MealPilot app: chefs, recipes,
ingredients, nutrition we can stand behind, dietary tags, costs and meal-prep info.
The app reads it through the `v_*` views.

**Team:**
- Aiman owns this database.
- The app is a separate project (iOS + Android, one codebase for Indonesia and the
  US). It owns user accounts, plans, tracking, payments and Veny.
- Medina owns the PRD: "MealPilot App — PRD v2", 2026-10-26. Requirement IDs
  (US-xx, NE-xx, TC-xx) in comments refer to it.
- Arini owns design.

The first version was built for Indonesia and lives at
`C:\Users\Aiman\OneDrive\Documents\mealpilot-data`
(github.com/aimanyamanie/mealpilot-data): a Python pipeline on Postgres (Neon,
Singapore) that turned Indonesian YouTube recipes into structured data. Read it
for lessons, but do not copy it wholesale; its rules were tuned to Indonesian
food.

## Keep this file short

Claude reads this file at the start of every session. The Indonesian version's
CLAUDE.md grew to 900 KB because every investigation was written up here.
- This file holds **current rules and how to run things**, nothing else.
- Write up investigations, measurements and retracted findings in
  `docs/decisions/YYYY-MM-DD-topic.md`, and add a one-line rule here only if it
  changes how future work should be done.
- When a rule here stops being true, delete it.

## Status

Scope decided 2026-10-29 (`docs/decisions/2026-10-29-prd-v2-scope.md`): catalogue
only, in a separate US database (Neon, US East), kept merge-ready with the
Indonesian one through `market` columns.

Done so far:
- `pipeline/schema.sql`, `views.sql` and `units.csv`, applied to Neon on 2026-10-29.
- The first ingredient seed (225 ingredients, 512 portions) from USDA bulk data,
  loaded the same day (`docs/decisions/2026-10-29-ingredient-seed.md`). Every row
  still needs a human sign-off on nutrition and allergens.

- The recipe-card loader and the creator permissions register, tested on our own
  sample cards. No creator has granted permission yet.

- Frying-oil rule and USDA FSIS storage defaults, in both loaders.

Next: steps in our own words, portion descriptions, and cost.

## Neon

- Project `mealpilot-us` (`patient-thunder-66435711`), region `aws-us-east-2`, branch
  `main`. This folder is linked through `.neon`, which is gitignored.
- `neon env pull` refreshes `DATABASE_URL` in `.env`.
- The project-scoped Neon MCP server is in `.mcp.json` and uses OAuth, so no key
  is stored there. The Neon skills are in `.claude/skills/`; run
  `neon skills update` to refresh them.

## Layout

- `pipeline/`: Python 3, run offline. Schema, views, seeds, loaders.
- `docs/decisions/`: dated write-ups of decisions and investigations.
- The app team reads only the views listed at the top of `pipeline/views.sql`.
  Changing a view's columns changes their contract: tell them.

## Rules carried over from the Indonesian version

These cost real bugs to learn. They still apply.

- **Never publish a number we cannot source.** Every ingredient records
  `nutrition_source`, `source_ref`, `data_quality`
  (`verified` / `researched` / `derived` / `estimated`) and who checked it.
  "We don't know yet" must be representable.
- **Picking the source record is the dangerous step.** A USDA search returns
  several candidates. Read the record's `description` against what the
  ingredient means, then check the macros fit the food. Matching energy values
  prove nothing if the wrong record was copied faithfully (the old project once
  had chicken thigh pointing at "Chicken, skin").
- **Store quantities as the source states them**, plus how many servings that
  makes. Per-portion figures are derived when read, never stored. A wrong
  serving count should be a one-field fix.
- **One master row per real-world ingredient**, with aliases doing the matching
  ("scallion" | "green onion" | "spring onion"). Missing aliases fail silently,
  so treat alias coverage as a measured metric.
- **A line we cannot convert to grams is a failure, not an exemption.** Coverage
  counts every line that states an amount. Below the threshold the recipe is
  held, not shown with a quietly low calorie count.
- **Keep fractions exact in the nutrition math.** Round only for display.
- **Generated counts in docs come from the database**, not from hand edits.

## Recipe sourcing (decided 2026-10-29)

See `docs/decisions/2026-10-29-recipe-sourcing.md`.

- **Recipe data comes from creators under a written licence:** their recipe cards
  (schema.org `Recipe`, often WP Recipe Maker), as an export or by permission to
  read them. `recipes.recipe_page_url` is the source.
- **Never build or keep ingredient, servings or nutrition data from YouTube Data
  API responses.** YouTube's Developer Policies limit stored API data to 30 days
  (III.E.4.d) and forbid deriving new data from it (III.E.4.h). No scraping of
  YouTube either (III.E.6).
- **The YouTube API is only for** the embedded player and display metadata (title,
  thumbnail, duration, availability), keyed by `video_id`. Refresh it at least
  every 30 days; `video_checked_at` records when. The refresh also sets
  `video_status`.
- **Creators to approach first:** Clean & Delicious, Feelgoodfoodie,
  Downshiftology, Sip and Feast, The Protein Chef. For vegetarian depth, add The
  Mediterranean Dish or Vegan Richa.
- **We recompute nutrition from USDA.** A creator's own calorie figure is a
  cross-check only, never the published number.

**Test-only exception (Aiman's decision, 2026-10-29).** For internal testing,
the pipeline may fetch video descriptions through the YouTube Data API and parse
them, as the Indonesian version did. The guardrails:
- That data lives only on the Neon branch `dev-youtube-test`, never `main`.
  `youtube_test.py` refuses to connect anywhere else.
- Raw API responses go to `pipeline/data/youtube/` (gitignored).
  `purge_youtube.py` deletes anything fetched more than 30 days ago.
- Creators stay `permission_status = 'none'`, so `v_published_recipes` shows
  none of it.
- Nothing from that branch is copied to `main`. A recipe goes to `main` only
  after it has been sourced again under a licence or written up by hand.

## US-market specifics

- **Units:** recipes use cups, tbsp, tsp, oz, lb, fl oz, sticks of butter, cans,
  and "1 medium onion". Converting volume to grams needs per-ingredient
  densities and piece weights. USDA FoodData Central `foodPortions` covers many
  of these, so cite it instead of guessing.
- **Display:** USD, °F, MM/DD/YYYY, US spelling.
- **Nutrition source:** USDA FoodData Central (Foundation + SR Legacy) is
  primary. It is public domain (CC0), so we can store it. Use Branded Foods
  only for packaged products that are actually used as ingredients.
- **Allergens:** the FDA's 9 major allergens: milk, eggs, fish, crustacean
  shellfish, tree nuts, peanuts, wheat, soybeans, sesame (added 2023 by the
  FASTER Act).
- **Dietary tags (PRD, US market):** vegetarian, vegan, gluten-free, dairy-free,
  kosher, halal, plus no pork, no beef and no seafood. Halal and kosher are
  derived as "compatible" from ingredients only; certification is an open
  question. From the old spec: a plan needs about 40–50 usable recipes per
  filter combination, so tell the app team which tags the catalogue can fill.
- **Every recipe needs:**
  - nutrition per portion: kcal, protein, carb, fat, fiber, sugar, sodium;
  - our own written steps;
  - prep and cook minutes, difficulty;
  - fridge and freezer days, reheat method;
  - a portion in household measures;
  - cost per serving in USD;
  - a nutritionist sign-off before publishing.
- **Regulatory, check before launch:** don't make health or "healthy" claims
  without checking FDA rules. If we store diet, weight or health goals, the FTC
  Health Breach Notification Rule and state consumer-health-data laws
  (Washington's My Health My Data Act, CCPA/CPRA) may apply.
- **Infrastructure:** host the database in a US region.

## Open decisions

Fill these in as they are made, then move each into the right section above.

- [ ] Lawyer review of the creator licence template before signing the first
      creator (questions in section 3 of the sourcing doc)
- [ ] Where US ingredient prices come from (cost per serving), and how often
      they're refreshed
- [ ] Who sets fridge and freezer days and reheat methods (USDA FSIS charts
      vs per recipe), and who the reviewing nutritionist is
- [ ] Frying oil: how much of the frying oil to count as absorbed. Until this is
      decided, those calories are left out and the recipe is held
      (`frying_oil_absorption_unknown`)
- [ ] Halal and kosher: is ingredient-level "compatible" enough, or do we need
      certified meat? (Medina)
- [ ] The off-plan food database (US-17: US restaurant chains and packaged
      foods). Is it in this catalogue, and from which licensed source?

## How to run

```bash
cd pipeline
python -m pip install -r requirements.txt
python -m pytest -q tests          # run before every commit
python apply_sql.py schema.sql     # once, on an empty database
python apply_sql.py views.sql      # after any view change; safe to re-run

# Ingredient seed (USDA bulk JSON in data/usda/, gitignored)
python usda.py index               # once after downloading the USDA JSON
python usda.py search chicken thigh  # candidates; read the description before picking
python build_seed.py               # ingredient_list.csv + usda_picks.csv -> *_seed.csv
python validate_seed.py            # 0 errors before every load
python load_seed.py                # upserts units and ingredients, replaces portions
```

Human sign-off of the seed:

```bash
python make_review_sheet.py        # -> review/ingredient_review_<date>.xlsx (gitignored)
python apply_review.py review/ingredient_review_<date>.xlsx   # -> signoffs.csv, portion_signoffs.csv
python build_seed.py && python validate_seed.py && python load_seed.py
```

- A sign-off holds only while what was approved is unchanged: the same FDC id
  for nutrition, the same allergen and diet flags, the same portion grams. If any
  of these change, `build_seed.py` prints "sign-off no longer applies" and the row
  needs a new review.
- "Fix" rows go to `review/fixes_<date>.md` and are corrected in
  `ingredient_list.csv` or `usda_picks.csv`.
- `signoffs.csv` and `portion_signoffs.csv` are the record of who approved what:
  commit them.

Licensed recipe cards (`docs/decisions/2026-10-29-recipe-card-loader.md`):

```bash
python permissions.py                              # check permissions.csv, sync status to main
python fetch_card.py <creator> <recipe page URL>   # refuses unless recipe_data is granted
python load_cards.py <creator>                     # data/cards/<creator>/ -> main, in_review
python load_cards.py --test tests/cards            # our own sample cards -> dev-youtube-test
```

- **Creator approvals:**
  - Save screenshots or agreements in `permissions/evidence/` (gitignored).
  - Add a row to `permissions.csv` with status, date, channel, scope (`recipe_data`
    at least), evidence file and who obtained it.
  - Run `python permissions.py`.
- **Grams and nutrition rules** live in `recipe_store.py`, shared by both loaders.

YouTube test pipeline (test branch only; see the test-only exception above):

```bash
python fetch_youtube.py --limit 50   # test_channels.csv -> data/youtube/*.json
python load_recipes.py               # -> dev-youtube-test: lines, grams, nutrition, holds
python purge_youtube.py              # run weekly: drops anything over 30 days old
```

Every parser bug becomes a case in `tests/golden_lines.json`.

Schema changes to the live database go in `pipeline/migrations/` (dated, safe to
re-run) **and** in `schema.sql`.

To add an ingredient, add a row to `ingredient_list.csv`, then pick its record
into `usda_picks.csv` (add a `pick_note` when it isn't the obvious match), then
build, validate and load. Never edit `*_seed.csv` by hand: they're generated.

## Schema rules

- Every column lives in `schema.sql`. Loaders never `ALTER TABLE`.
- Grams on a line are NULL when unknown, never 0. Lookup order: mass unit, then the
  exact `ingredient_portions` row, then that unit's default portion, then density.
- Allergen and diet flags come only from matched, reviewed ingredients
  (`v_recipe_flags.flags_known`). Unknown is never shown as "free".
- A recipe is visible only if all of these hold: its creator's
  `permission_status = 'granted'`, every nutrition field is present, it has a
  nutritionist sign-off, and all its steps are rewritten.
- Steps are our own wording. `steps.source_text` is never exposed.

## Secrets

`.env` holds credentials and is gitignored. Commit a `.env.example` with
empty values instead.
