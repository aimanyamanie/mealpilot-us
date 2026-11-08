-- MealPilot US recipe catalogue. Fresh start 2026-11-08.
-- Run once on an empty database:  python apply_sql.py schema.sql
-- Nutrition per serving is never stored: views.sql derives it from grams.

-- ---------- reference ----------

create table units (
    code    text primary key,                  -- 'cup', 'tbsp', 'lb', 'clove'
    kind    text not null check (kind in ('mass', 'volume', 'count')),
    grams   numeric,                           -- mass units only
    ml      numeric,                           -- volume units only
    aliases text[] not null default '{}',
    check ((kind = 'mass') = (grams is not null)),
    check ((kind = 'volume') = (ml is not null))
);

create table nutrients (
    number text primary key,                   -- USDA nutrient number: '208' = energy kcal
    name   text not null,
    unit   text not null
);

-- FDA major allergens (FALCPA + FASTER Act 2023).
create table allergens (code text primary key);
insert into allergens values ('milk'), ('egg'), ('fish'), ('shellfish'), ('tree_nuts'),
    ('peanuts'), ('wheat'), ('soy'), ('sesame');

-- ---------- ingredients ----------

create table ingredients (
    id              serial primary key,
    slug            text not null unique,
    name            text not null,
    category        text not null,
    -- what diet tags are derived from
    food_group      text not null check (food_group in ('plant', 'mineral', 'dairy', 'egg',
                        'honey', 'poultry', 'beef', 'pork', 'lamb', 'other_meat', 'fish',
                        'shellfish')),
    gluten          boolean not null,
    animal_rennet   boolean not null default false,   -- many hard cheeses: not vegetarian
    alcohol         boolean not null default false,
    -- where the nutrition comes from
    fdc_id          integer not null,
    fdc_description text not null,                    -- read it: picking the record is the risky step
    fdc_data_type   text not null,
    pick_note       text,
    reviewed_by     text,                             -- null = nobody has checked this row
    reviewed_at     timestamptz,
    updated_at      timestamptz not null default now()
);

create table ingredient_aliases (
    alias         text primary key,                   -- lower case
    ingredient_id integer not null references ingredients on delete cascade
);

create table ingredient_allergens (
    ingredient_id integer not null references ingredients on delete cascade,
    allergen      text not null references allergens,
    primary key (ingredient_id, allergen)
);

create table ingredient_nutrients (
    ingredient_id   integer not null references ingredients on delete cascade,
    nutrient_number text not null references nutrients,
    per_100g        numeric not null,                 -- as USDA publishes it
    primary key (ingredient_id, nutrient_number)
);

-- Household measures: 1 <unit> [<qualifier>] of this ingredient weighs grams_per_unit.
create table ingredient_portions (
    id             serial primary key,
    ingredient_id  integer not null references ingredients on delete cascade,
    unit           text not null references units,
    qualifier      text not null default '',          -- 'fluid', 'grated', 'with skin'
    grams_per_unit numeric not null check (grams_per_unit > 0),
    source_fdc_id  integer not null,
    source_note    text not null,                     -- the USDA label, or why it was borrowed
    unique (ingredient_id, unit, qualifier)
);

-- ---------- creators and sources ----------

create table chefs (
    id                 serial primary key,
    slug               text not null unique,
    name               text not null,
    youtube_channel_id text unique,
    youtube_url        text,
    website_url        text,
    market             text not null default 'US'
);

create table sources (
    id                serial primary key,
    chef_id           integer not null references chefs,
    kind              text not null check (kind in ('youtube_transcript')),
    video_id          text not null unique,
    title             text not null,
    url               text not null,
    thumbnail_url     text,
    length_seconds    integer,
    language          text,
    transcript        jsonb not null,                 -- internal only; never exposed to the app
    transcript_sha256 text not null,
    received_at       timestamptz not null default now()
);

-- ---------- recipes ----------

create table recipes (
    id              serial primary key,
    slug            text not null unique,
    market          text not null default 'US',
    chef_id         integer not null references chefs,
    source_id       integer references sources,
    title           text not null,
    summary         text,                             -- our words
    cuisine         text,
    course          text check (course in ('breakfast', 'main', 'side', 'snack', 'dessert', 'drink')),
    meal_slots      text[] not null default '{}',     -- breakfast, lunch, dinner, snack
    servings        numeric not null check (servings > 0),
    servings_basis  text not null check (servings_basis in ('stated', 'estimated')),
    prep_minutes    integer,
    cook_minutes    integer,
    times_basis     text check (times_basis in ('stated', 'estimated')),
    difficulty      text check (difficulty in ('easy', 'medium', 'hard')),
    fridge_days     integer,
    freezer_days    integer,
    reheat          text,
    cost_per_serving_usd numeric,
    notes           text,                             -- internal: what was guessed and why
    status          text not null default 'needs_review'
                        check (status in ('draft', 'needs_review', 'approved', 'published')),
    extracted_by    text not null,
    extracted_at    timestamptz not null default now(),
    reviewed_by     text,
    reviewed_at     timestamptz
);

create table recipe_ingredients (
    id              serial primary key,
    recipe_id       integer not null references recipes on delete cascade,
    position        integer not null,
    group_label     text,                             -- 'Chicken', 'Sauce'
    ingredient_id   integer references ingredients,   -- null = not matched yet
    display_text    text not null,                    -- what the app shows: '2 cups heavy cream'
    quantity        numeric,                          -- null for 'to taste'
    unit            text references units,
    qualifier       text,                             -- picks the portion: 'fluid', 'grated'
    preparation     text,                             -- 'finely chopped'
    quantity_basis  text not null check (quantity_basis in ('stated', 'estimated', 'to_taste')),
    grams           numeric,                          -- null = unknown, never 0
    grams_method    text check (grams_method in ('mass', 'portion', 'volume_scaled')),
    portion_id      integer references ingredient_portions,
    in_nutrition    boolean not null default true,
    excluded_reason text,                             -- required when in_nutrition is false
    optional        boolean not null default false,
    evidence        text,                             -- transcript words this line rests on
    evidence_sec    numeric,                          -- where in the video
    unique (recipe_id, position),
    check (in_nutrition or excluded_reason is not null),
    check ((grams is null) = (grams_method is null))
);

create table recipe_steps (
    recipe_id   integer not null references recipes on delete cascade,
    step_no     integer not null,
    text        text not null,                        -- our own wording
    start_sec   numeric,                              -- jump point in the video
    primary key (recipe_id, step_no)
);
