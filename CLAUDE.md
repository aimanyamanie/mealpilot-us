# MealPilot US: recipe catalogue database

The US market's recipe catalogue for the MealPilot app: chefs, recipes,
ingredients, nutrition, diet tags. The app reads it through the views at the top
of `pipeline/views.sql`. Aiman owns this database; the app (iOS + Android) is a
separate project.

**Fresh start, 2026-11-08** (`docs/decisions/2026-11-08-fresh-start-transcripts.md`).
The first build (Oct 29–30) is in git history, in the Neon branch
`archive-v1-2026-10-30`, and in the `archive_v1` schema on `main`.

Keep this file short: current rules and how to run things. Write investigations
up in `docs/decisions/YYYY-MM-DD-topic.md`.

## How a recipe gets in

1. Aiman supplies a YouTube transcript JSON (`video_id`, `transcript[]` of
   `{text, start, duration}`, `metadata`). Save it as
   `pipeline/data/transcripts/<video_id>.json` (gitignored; the loader also
   stores it in `sources.transcript`).
2. Claude extracts the recipe into `pipeline/recipes/<slug>.json` (format: copy
   the Chicken Alfredo file). Rules for extraction:
   - Every ingredient line has `basis`: `stated` (the creator said the amount),
     `estimated` (we chose it), or `to_taste` (no amount).
   - Every line quotes the transcript words it rests on (`evidence`, pieces
     joined with `...`) and their time `t`. The loader rejects quotes that are
     not in the transcript within 20 s of `t`.
   - Write down every guess and why in `notes`: servings, times, ambiguous
     amounts, what was left out.
   - Steps are in our own words, with `t` as the video jump point.
   - Lines that don't end up eaten (pasta-water salt, garnish with no amount)
     set `in_nutrition: false` and an `excluded_reason`.
3. New ingredients go in `ingredients.csv` first (see below).
4. `python load_recipe.py --check recipes/<slug>.json`, then without `--check`.

## Nutrition rules

- **Source is USDA FoodData Central** (SR Legacy, Foundation), public domain.
  Picking the record is the risky step: read its `description`. `usda.py show`
  once returned *fried, battered* thigh for a guessed raw-thigh id.
- Store amounts as stated plus servings; per-serving numbers are computed in the
  views, never stored. Exact math; round only in `v_recipe_card`.
- Grams are NULL when unknown, never 0. A counted line without grams makes
  the nutrition NULL and the recipe `draft`.
- A portion's qualifier decides its weight (cream: fluid cup 238 g, whipped cup
  120 g). If a unit has several portions, the line must name the qualifier.
- A weight USDA lacks goes in `extra_portions.csv` with its source.
- Diet tags and allergens come from matched ingredients only; unknown is never
  shown as "free". Parmigiano and Pecorino use animal rennet, so they're not vegetarian.
- Status: `needs_review` after loading. Nobody has reviewed an ingredient or
  recipe yet (`reviewed_by` is null everywhere).

## How to run

```bash
cd pipeline
python -m pip install -r requirements.txt
python -m pytest -q -p no:warnings tests     # before every commit
python usda.py search chicken thigh raw      # find candidates; read descriptions
python usda.py show 172385                   # nutrients and household portions
python load_ingredients.py                   # units + ingredients.csv + USDA -> db
python apply_sql.py views.sql                # after any view change
python load_recipe.py recipes/<slug>.json
```

`schema.sql` runs once on an empty schema. Schema changes to the live database
go in `pipeline/migrations/` (dated) and in `schema.sql`.

## Neon

- Project `mealpilot-us` (`patient-thunder-66435711`), `aws-us-east-2`, branch `main`.
- `.env` holds `DATABASE_URL` and `FDC_API_KEY` (gitignored; see `.env.example`).
  Refresh the URL with `neon connection-string main --project-id patient-thunder-66435711`.
- Without `FDC_API_KEY`, USDA calls use DEMO_KEY (30 an hour). Records are cached
  in `pipeline/data/usda/`.

## Open questions

- [ ] Transcripts give few amounts (28% of the Alfredo's grams were stated).
      Do we accept estimated amounts in published recipes, or cross-check
      against the creator's written recipe first?
- [ ] Who reviews ingredients and recipes before `approved`?
- [ ] Creator permission: transcript-based recipes are in `main` by Aiman's
      decision of 2026-11-08; the earlier licence-only rule is suspended.
- [ ] Fridge/freezer days, reheat method, cost per serving: columns exist, no source yet.
