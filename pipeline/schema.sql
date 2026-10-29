-- MealPilot US: recipe catalogue schema.
-- Postgres. Run once against an empty database (python apply_sql.py schema.sql).
--
-- SCOPE: the US market's catalogue (chefs, recipes, ingredients, nutrition,
-- tags, costs) that the MealPilot app reads. User accounts, plans, tracking
-- and subscriptions belong to the app team's database, not this one.
-- Requirement IDs (US-xx, NE-xx, TC-xx) refer to Medina's PRD v2 (2026-10-26).
--
-- Every column lives in this file. Loaders never ALTER TABLE: in the
-- Indonesian version, columns added at load time meant this file stopped
-- describing the real database.
--
-- This is a separate database from the Indonesian one. `market` is still
-- carried on creators and recipes so the two catalogues can be merged later
-- without rewriting rows.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------
-- CREATORS: the YouTube chefs we have permission to use.
-- ---------------------------------------------------------------
CREATE TABLE creators (
  id                bigserial PRIMARY KEY,
  slug              text UNIQUE NOT NULL,
  market            text NOT NULL DEFAULT 'US' CHECK (market IN ('US', 'ID')),
  display_name      text NOT NULL,
  tagline           text,                     -- 'American · high-protein comfort food'
  channel_id        text UNIQUE,              -- YouTube channel ID
  channel_name      text,
  channel_url       text,
  website_url       text,
  avatar_url        text,
  subscriber_count  integer,                  -- refreshed by the pipeline
  is_tracked        boolean NOT NULL DEFAULT true,  -- the pipeline polls this channel
  -- Written permission on file, and where. A recipe from a creator without
  -- it is never published (PRD: content rights, partner agreements).
  permission_status text NOT NULL DEFAULT 'none'
    CHECK (permission_status IN ('none', 'requested', 'granted', 'declined')),
  permission_ref    text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------
-- UNITS: loaded from units.csv. Small and static, so load it first.
-- ---------------------------------------------------------------
CREATE TYPE unit_kind AS ENUM ('mass', 'volume', 'count', 'subjective');

CREATE TABLE units (
  id              bigserial PRIMARY KEY,
  slug            text UNIQUE NOT NULL,     -- 'tbsp'
  name            text NOT NULL,            -- 'tablespoon'
  plural          text NOT NULL,            -- 'tablespoons'
  kind            unit_kind NOT NULL,
  -- mass: grams per 1 unit. volume: ml per 1 unit. count/subjective: NULL,
  -- because a clove or a can weighs what the ingredient says it weighs.
  factor_to_base  numeric(12,5),
  aliases         text,                     -- pipe-separated, for matching
  CONSTRAINT factor_required_for_measured
    CHECK ((kind IN ('mass', 'volume') AND factor_to_base IS NOT NULL)
        OR (kind IN ('count', 'subjective') AND factor_to_base IS NULL))
);

-- ---------------------------------------------------------------
-- INGREDIENTS: the master table. One row per real-world ingredient,
-- reused by every recipe. Loaded from ingredients_seed.csv; the app
-- never writes it.
-- ---------------------------------------------------------------
CREATE TABLE ingredients (
  id                  bigserial PRIMARY KEY,
  slug                text UNIQUE NOT NULL,   -- 'chicken-thigh-boneless-skinless'
  name                text NOT NULL,          -- 'Chicken thigh, boneless, skinless'
  aliases             text,                   -- 'boneless chicken thighs|chicken thighs'
  category            text NOT NULL,

  -- Nutrition per 100 g EDIBLE portion. NULL means not sourced yet, never 0.
  kcal_100g           numeric(8,2),
  protein_100g        numeric(8,2),
  carb_100g           numeric(8,2),
  fat_100g            numeric(8,2),
  fiber_100g          numeric(8,2),
  sugar_100g          numeric(8,2),           -- total sugars, as USDA reports them
  sodium_mg_100g      numeric(8,2),
  negligible_calorie  boolean NOT NULL DEFAULT false,  -- water, ice, salt
  -- Alcohol carries energy outside protein/carb/fat; baking soda's carbohydrate
  -- is not metabolised. The reason the Atwater check is skipped, or NULL.
  macro_check_exempt  text,

  -- Conversions. Volume to grams uses density unless ingredient_portions
  -- has a better figure for that exact measure.
  density_g_per_ml    numeric(6,3),
  edible_pct          numeric(5,2) NOT NULL DEFAULT 100,  -- bone, peel, pit
  -- false for items that cannot be halved in practice (egg, garlic clove).
  -- Nutrition uses the exact fraction; only the cooking view rounds.
  is_divisible        boolean NOT NULL DEFAULT true,

  -- Allergens: the FDA's 9 major allergens. Only trustworthy where
  -- allergens_reviewed is true. An unreviewed ingredient makes its recipes
  -- "allergens unknown", never "allergen-free".
  has_milk            boolean NOT NULL DEFAULT false,
  has_egg             boolean NOT NULL DEFAULT false,
  has_fish            boolean NOT NULL DEFAULT false,
  has_shellfish       boolean NOT NULL DEFAULT false,   -- crustacean shellfish
  has_tree_nut        boolean NOT NULL DEFAULT false,
  has_peanut          boolean NOT NULL DEFAULT false,
  has_wheat           boolean NOT NULL DEFAULT false,
  has_soy             boolean NOT NULL DEFAULT false,
  has_sesame          boolean NOT NULL DEFAULT false,
  -- Gluten is not an FDA major allergen and is not the same as wheat
  -- (barley and rye have it; wheat-free is not gluten-free).
  has_gluten          boolean NOT NULL DEFAULT false,
  -- For the halal tag (wine, mirin, beer, vanilla extract).
  has_alcohol         boolean NOT NULL DEFAULT false,
  -- Diet. NULL = plant or mineral. pork and beef are split out of meat
  -- because "no pork" and "no beef" are tags in their own right.
  animal_source       text CHECK (animal_source IS NULL OR animal_source IN
                        ('pork', 'beef', 'other_meat', 'poultry', 'fish', 'shellfish',
                         'dairy', 'egg', 'honey', 'other_animal')),
  allergens_reviewed  boolean NOT NULL DEFAULT false,
  allergens_note      text,                   -- e.g. 'varies by brand; label checked: ...'

  -- Shopping (US-14). Kept apart from nutrition on purpose: what is worth
  -- buying and what carries calories are different decisions.
  store_section       text CHECK (store_section IS NULL OR store_section IN
                        ('produce', 'meat-seafood', 'dairy-eggs', 'bakery', 'pantry',
                         'spices', 'frozen', 'other')),
  shop_unit           text,                   -- how it is sold: 'bag (2 lb)', 'can (15 oz)'
  shop_unit_grams     numeric(10,2),          -- grams in one shop_unit
  shopping_exempt     boolean NOT NULL DEFAULT false,  -- water, ice
  shopping_exempt_reason text,

  -- Cost (US-09 cost per portion). A typical US retail price for one
  -- shop_unit, and where it came from. Cost per portion is derived from this.
  price_usd           numeric(8,2),
  price_source        text,                   -- 'BLS average price, 2026-09' / 'Walmart.com, 2026-10-20'
  price_checked_on    date,

  -- Provenance. This is a health product: where every number came from must
  -- be answerable.
  nutrition_source    text NOT NULL DEFAULT 'UNSOURCED'
    CHECK (nutrition_source IN ('USDA', 'LABEL', 'DERIVED', 'ESTIMATE', 'UNSOURCED')),
  source_ref          text,                   -- FDC id, or product + label date
  source_version      text,                   -- FDC release, e.g. 'FDC 2025-04' (NE-39)
  source_description  text,                   -- the record's own description, as read
  data_quality        text NOT NULL DEFAULT 'estimated'
    CHECK (data_quality IN ('verified', 'researched', 'derived', 'estimated')),
  needs_verification  boolean NOT NULL DEFAULT true,
  verified_at         timestamptz,
  verified_by         text,
  notes               text,                   -- derivation formula, portion source

  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),

  -- A verified row cites its record. Copying the wrong record faithfully
  -- is still possible, which is why source_description is kept to re-read.
  CONSTRAINT verified_needs_ref
    CHECK (data_quality <> 'verified' OR (source_ref IS NOT NULL AND verified_by IS NOT NULL))
);

CREATE INDEX ingredients_category_idx ON ingredients (category);
CREATE INDEX ingredients_name_trgm ON ingredients USING gin (name gin_trgm_ops);

-- ---------------------------------------------------------------
-- INGREDIENT_PORTIONS: grams for one specific measure of one ingredient.
-- US recipes measure by volume and by the piece, and one density per
-- ingredient is not enough: a cup of chopped onion and a cup of minced onion
-- weigh different amounts, and "1 medium onion" vs "1 large onion" are
-- different counts. USDA FoodData Central publishes these as foodPortions.
-- ---------------------------------------------------------------
CREATE TABLE ingredient_portions (
  id              bigserial PRIMARY KEY,
  ingredient_id   bigint NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
  unit_id         bigint NOT NULL REFERENCES units(id),
  -- '' when the measure has no qualifier. Sizes ('small' / 'medium' / 'large')
  -- and prep ('chopped', 'packed') go here.
  modifier        text NOT NULL DEFAULT '',
  grams           numeric(10,3) NOT NULL CHECK (grams > 0),
  source          text NOT NULL CHECK (source IN ('USDA', 'LABEL', 'MEASURED', 'ESTIMATE')),
  source_ref      text,                     -- FDC id + portion description
  is_default      boolean NOT NULL DEFAULT false,  -- used when the line gives no modifier
  notes           text,
  -- Human sign-off of this weight (review workbook -> portion_signoffs.csv).
  reviewed_by     text,
  reviewed_at     date,
  UNIQUE (ingredient_id, unit_id, modifier)
);

-- At most one default per (ingredient, unit).
CREATE UNIQUE INDEX ingredient_portions_one_default
  ON ingredient_portions (ingredient_id, unit_id) WHERE is_default;

-- ---------------------------------------------------------------
-- INGREDIENT_SUBSTITUTES (NE-37): what to use when an ingredient is hard
-- to find in the US, e.g. an Indonesian recipe offered as a cuisine.
-- The recipe's nutrition is recalculated with the substitute.
-- ---------------------------------------------------------------
CREATE TABLE ingredient_substitutes (
  id                bigserial PRIMARY KEY,
  ingredient_id     bigint NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
  substitute_id     bigint NOT NULL REFERENCES ingredients(id),
  grams_ratio       numeric(6,3) NOT NULL DEFAULT 1,  -- grams of substitute per gram replaced
  notes             text,
  UNIQUE (ingredient_id, substitute_id),
  CHECK (ingredient_id <> substitute_id)
);

-- ---------------------------------------------------------------
-- RECIPES
-- ---------------------------------------------------------------
CREATE TYPE recipe_status AS ENUM
  ('discovered', 'extracted', 'in_review', 'published', 'rejected');

CREATE TABLE recipes (
  id                  bigserial PRIMARY KEY,
  slug                text UNIQUE NOT NULL,
  market              text NOT NULL DEFAULT 'US' CHECK (market IN ('US', 'ID')),
  title               text NOT NULL,
  creator_id          bigint REFERENCES creators(id),
  cuisine             text,                 -- 'American', 'Mexican', 'Indonesian'
  recipe_type         text CHECK (recipe_type IS NULL OR recipe_type IN
                        ('meal', 'side', 'dessert', 'component', 'drink', 'snack')),
  meal_slots          text[] CHECK (meal_slots IS NULL OR meal_slots <@
                        ARRAY['breakfast', 'lunch', 'dinner', 'snack']::text[]),
  plannable           boolean NOT NULL DEFAULT false,
  is_guest_sample     boolean NOT NULL DEFAULT false,  -- one of the guest-browse recipes (US-04)

  -- Source video. NE-15: when it goes private or is removed, video_status
  -- changes and the recipe goes to review; the written steps stay usable.
  video_id            text UNIQUE,
  video_url           text,
  video_duration_seconds integer,
  video_status        text NOT NULL DEFAULT 'available'
    CHECK (video_status IN ('available', 'unavailable', 'region_blocked')),
  video_checked_at    timestamptz,
  recipe_page_url     text,                 -- creator's own written recipe, if linked
  thumbnail_url       text,
  published_on        date,

  -- THE CRITICAL FIELD. Quantities in recipe_ingredients are stored as the
  -- source states them, for this many servings. Per-portion is derived on
  -- read. A wrong serving count is fixed here, in one field.
  source_servings     numeric(6,2) NOT NULL DEFAULT 1 CHECK (source_servings > 0),
  servings_confidence text CHECK (servings_confidence IS NULL OR servings_confidence IN
                        ('stated', 'decided', 'inferred', 'guess')),
  servings_evidence   text,                 -- e.g. 'recipe card: "Serves 4"'

  -- Cooking and meal-prep info (US-09, US-13)
  prep_minutes        integer CHECK (prep_minutes >= 0),
  cook_minutes        integer CHECK (cook_minutes >= 0),
  difficulty          text CHECK (difficulty IS NULL OR difficulty IN ('easy', 'medium', 'hard')),
  fridge_days         smallint CHECK (fridge_days >= 0),   -- safe days refrigerated
  freezer_days        smallint CHECK (freezer_days >= 0),  -- NULL = do not freeze
  storage_source      text,                 -- 'USDA FSIS cold storage chart' / 'creator'
  reheat_method       text,                 -- 'Microwave 90 sec, stir halfway'
  -- One portion in household measures (US-09), written for this recipe:
  -- '1½ cups cooked rice + 6 large shrimp + a fist of broccoli'
  portion_description text,

  status              recipe_status NOT NULL DEFAULT 'discovered',
  hold_reasons        text[],               -- which publish gates failed
  review_notes        text,
  -- PRD: every recipe's nutrition is reviewed by a nutritionist before publishing.
  nutrition_reviewed_by text,
  nutrition_reviewed_at timestamptz,
  published_at        timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX recipes_status_idx ON recipes (status);
CREATE INDEX recipes_creator_idx ON recipes (creator_id);

-- ---------------------------------------------------------------
-- RECIPE_INGREDIENTS: one ingredient line in one recipe. Scaling,
-- nutrition and the shopping list all start here.
-- ---------------------------------------------------------------
CREATE TABLE recipe_ingredients (
  id                  bigserial PRIMARY KEY,
  recipe_id           bigint NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
  display_order       integer NOT NULL DEFAULT 0,
  raw_text            text NOT NULL,        -- '2 large yellow onions, diced'. Always kept
  group_label         text,                 -- 'For the sauce'

  -- Parsed, AS STATED for recipes.source_servings
  quantity            numeric(10,3),
  quantity_max        numeric(10,3),        -- the top of a range: '2-3 cloves'
  unit_id             bigint REFERENCES units(id),
  modifier            text NOT NULL DEFAULT '',  -- 'large', 'packed'; matches ingredient_portions
  ingredient_id       bigint REFERENCES ingredients(id),
  preparation_note    text,                 -- 'diced'
  is_optional         boolean NOT NULL DEFAULT false,
  is_scalable         boolean NOT NULL DEFAULT true,  -- false for 'to taste'

  -- Grams of this line, for the whole recipe. NULL when it could not be
  -- resolved: never 0, because 0 reads as "weighs nothing" and NULL reads
  -- as "we do not know".
  grams_as_purchased  numeric(10,2),        -- what the shopping list buys
  grams_edible        numeric(10,2),        -- what nutrition counts (after edible_pct)
  grams_method        text CHECK (grams_method IS NULL OR grams_method IN
                        ('mass', 'portion', 'density', 'override')),

  match_confidence    numeric(4,3),
  needs_review        boolean NOT NULL DEFAULT false,
  review_reason       text                  -- 'unmatched_ingredient' | 'no_grams' | 'ambiguous_unit' ...
);

CREATE INDEX ri_recipe_idx ON recipe_ingredients (recipe_id);
CREATE INDEX ri_ingredient_idx ON recipe_ingredients (ingredient_id);
CREATE INDEX ri_needs_review_idx ON recipe_ingredients (needs_review) WHERE needs_review;

-- ---------------------------------------------------------------
-- STEPS: our own written method (US-09). Never the creator's words:
-- source_text keeps what the step was written from and is never displayed.
-- ---------------------------------------------------------------
CREATE TABLE steps (
  id              bigserial PRIMARY KEY,
  recipe_id       bigint NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
  step_number     integer NOT NULL,
  instruction     text NOT NULL,            -- may embed {ri:ID} tokens for live quantities
  timer_seconds   integer,
  is_hands_off    boolean NOT NULL DEFAULT false,  -- oven, simmer: frees the cook (prep day, US-13)
  source_text     text,                     -- NEVER displayed
  needs_rewrite   boolean NOT NULL DEFAULT true,  -- only false steps are shown
  UNIQUE (recipe_id, step_number)
);

-- ---------------------------------------------------------------
-- RECIPE_NUTRITION: a cache, recomputed by the loader on any change.
-- PER SINGLE SERVING (already divided by source_servings).
-- ---------------------------------------------------------------
CREATE TABLE recipe_nutrition (
  recipe_id             bigint PRIMARY KEY REFERENCES recipes(id) ON DELETE CASCADE,
  per_serving_kcal      numeric(8,2),
  per_serving_protein   numeric(8,2),
  per_serving_carb      numeric(8,2),
  per_serving_fat       numeric(8,2),
  per_serving_fiber     numeric(8,2),
  per_serving_sugar     numeric(8,2),
  per_serving_sodium_mg numeric(8,2),
  total_kcal            numeric(10,2),      -- whole recipe, at source_servings
  -- Lines that state an amount and were converted to grams, over all lines
  -- that state an amount. A line that states an amount and could not be
  -- converted counts against coverage; it is never left out.
  coverage_ratio        numeric(4,3),
  -- Share of this recipe's grams whose ingredient is not yet verified.
  unverified_share      numeric(4,3),
  -- Which reference data produced these numbers (NE-39). A change to the
  -- reference triggers a recalculation and a review.
  reference_version     text,               -- 'FDC 2025-04'
  -- Cost per serving in USD, and the share of grams that had a price.
  per_serving_cost_usd  numeric(8,2),
  cost_coverage         numeric(4,3),
  computed_at           timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------
-- DAILY_VALUES: FDA Daily Values for the nutrition panel's %DV. Kept as
-- data so a revision of the reference is a row change, not a code change.
-- ---------------------------------------------------------------
CREATE TABLE daily_values (
  nutrient      text PRIMARY KEY,           -- 'fiber', 'sodium_mg', ...
  amount        numeric(10,2) NOT NULL,
  unit          text NOT NULL,              -- 'g' | 'mg'
  source        text NOT NULL,              -- '21 CFR 101.9, 2016 rule'
  notes         text
);
