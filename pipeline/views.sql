-- Views the app reads. Safe to re-run:  python apply_sql.py views.sql
--
-- App contract (tell the app team before changing these columns):
--   v_recipe_card         one row per recipe: header, per-serving nutrition, tags
--   v_recipe_ingredients  ingredient lines in order
--   v_recipe_steps        method steps in order
-- The others are building blocks.

drop view if exists v_recipe_card, v_recipe_ingredients, v_recipe_steps,
    v_recipe_flags, v_recipe_nutrition, v_recipe_nutrients cascade;

-- Every nutrient per serving, for every recipe. per_serving is null when the
-- figure is not trustworthy: a counted line has no grams or no ingredient, or
-- lines that lack this nutrient make up 1% or more of the recipe's grams.
-- Exact numeric math; round only for display. Negative USDA values (carbs by
-- difference can come out slightly below 0) count as 0.
create view v_recipe_nutrients as
with lines as (
    select ri.recipe_id, ri.ingredient_id, ri.grams
    from recipe_ingredients ri
    where ri.in_nutrition
), totals as (
    select recipe_id, sum(grams) as grams_total,
           bool_or(grams is null or ingredient_id is null) as any_unknown
    from lines group by recipe_id
)
select r.id as recipe_id, k.number, k.name, k.unit,
       case when not t.any_unknown
             and coalesce(sum(l.grams) filter (where n.per_100g is null), 0) < 0.01 * t.grams_total
            then sum(l.grams * greatest(n.per_100g, 0) / 100) / r.servings
       end as per_serving
from recipes r
join totals t on t.recipe_id = r.id
join lines l on l.recipe_id = r.id
cross join nutrients k
left join ingredient_nutrients n
       on n.ingredient_id = l.ingredient_id and n.nutrient_number = k.number
group by r.id, r.servings, k.number, k.name, k.unit, t.grams_total, t.any_unknown;

-- The headline panel, plus how much of the recipe rests on guessed amounts.
create view v_recipe_nutrition as
select r.id as recipe_id,
       max(n.per_serving) filter (where n.number = '208') as kcal,
       max(n.per_serving) filter (where n.number = '203') as protein_g,
       max(n.per_serving) filter (where n.number = '205') as carb_g,
       max(n.per_serving) filter (where n.number = '204') as fat_g,
       max(n.per_serving) filter (where n.number = '606') as sat_fat_g,
       max(n.per_serving) filter (where n.number = '291') as fiber_g,
       max(n.per_serving) filter (where n.number = '269') as sugar_g,
       max(n.per_serving) filter (where n.number = '307') as sodium_mg,
       max(n.per_serving) filter (where n.number = '601') as cholesterol_mg,
       q.grams_per_serving,
       q.stated_share,
       q.unreviewed_ingredients
from recipes r
left join v_recipe_nutrients n on n.recipe_id = r.id
left join lateral (
    select sum(ri.grams) / r.servings as grams_per_serving,
           sum(ri.grams) filter (where ri.quantity_basis = 'stated') / nullif(sum(ri.grams), 0)
               as stated_share,       -- share of counted grams the creator actually stated
           count(distinct ri.ingredient_id) filter (where i.reviewed_by is null)
               as unreviewed_ingredients
    from recipe_ingredients ri
    left join ingredients i on i.id = ri.ingredient_id
    where ri.recipe_id = r.id and ri.in_nutrition
) q on true
group by r.id, q.grams_per_serving, q.stated_share, q.unreviewed_ingredients;

-- Allergens and diet tags, from every line including optional ones.
-- All tag columns are null unless every line is matched to an ingredient:
-- unknown is never shown as "free".
create view v_recipe_flags as
with x as (
    select ri.recipe_id,
           bool_and(ri.ingredient_id is not null) as known,
           bool_or(i.food_group in ('poultry', 'beef', 'pork', 'lamb', 'other_meat', 'fish',
                                    'shellfish') or i.animal_rennet) as not_veg,
           bool_or(i.food_group in ('dairy', 'egg', 'honey')) as animal_product,
           bool_or(i.gluten) as gluten,
           bool_or(i.food_group = 'dairy') as dairy,
           bool_or(i.food_group = 'pork') as pork,
           bool_or(i.food_group = 'beef') as beef,
           bool_or(i.food_group in ('fish', 'shellfish')) as seafood,
           bool_or(i.alcohol) as alcohol
    from recipe_ingredients ri
    left join ingredients i on i.id = ri.ingredient_id
    group by ri.recipe_id
)
select x.recipe_id,
       x.known as flags_known,
       case when x.known then coalesce((
           select array_agg(distinct ia.allergen order by ia.allergen)
           from recipe_ingredients ri join ingredient_allergens ia using (ingredient_id)
           where ri.recipe_id = x.recipe_id), '{}') end as allergens,
       case when x.known then array_remove(array[
           case when not x.not_veg then 'vegetarian' end,
           case when not x.not_veg and not x.animal_product then 'vegan' end,
           case when not x.gluten then 'gluten_free' end,
           case when not x.dairy then 'dairy_free' end,
           case when not x.pork then 'no_pork' end,
           case when not x.beef then 'no_beef' end,
           case when not x.seafood then 'no_seafood' end,
           case when not x.alcohol then 'alcohol_free' end], null) end as diet_tags
from x;

create view v_recipe_card as
select r.slug, r.market, r.title, r.summary, r.cuisine, r.course, r.meal_slots,
       c.name as chef, c.slug as chef_slug,
       s.video_id, s.url as video_url, s.thumbnail_url,
       r.servings, r.servings_basis,
       r.prep_minutes, r.cook_minutes, r.prep_minutes + r.cook_minutes as total_minutes,
       r.times_basis, r.difficulty, r.fridge_days, r.freezer_days, r.reheat,
       r.cost_per_serving_usd,
       round(n.kcal) as kcal,
       round(n.protein_g, 1) as protein_g,
       round(n.carb_g, 1) as carb_g,
       round(n.fat_g, 1) as fat_g,
       round(n.sat_fat_g, 1) as sat_fat_g,
       round(n.fiber_g, 1) as fiber_g,
       round(n.sugar_g, 1) as sugar_g,
       round(n.sodium_mg) as sodium_mg,
       round(n.cholesterol_mg) as cholesterol_mg,
       round(n.grams_per_serving) as grams_per_serving,
       round(n.stated_share, 2) as stated_share,
       n.unreviewed_ingredients,
       f.allergens, f.diet_tags,
       r.status
from recipes r
join chefs c on c.id = r.chef_id
left join sources s on s.id = r.source_id
left join v_recipe_nutrition n on n.recipe_id = r.id
left join v_recipe_flags f on f.recipe_id = r.id;

create view v_recipe_ingredients as
select r.slug as recipe_slug, ri.position, ri.group_label, ri.display_text,
       ri.quantity, ri.unit, ri.preparation, ri.optional,
       round(ri.grams, 1) as grams, i.slug as ingredient_slug, i.name as ingredient
from recipe_ingredients ri
join recipes r on r.id = ri.recipe_id
left join ingredients i on i.id = ri.ingredient_id;

create view v_recipe_steps as
select r.slug as recipe_slug, st.step_no, st.text, st.start_sec
from recipe_steps st join recipes r on r.id = st.recipe_id;
