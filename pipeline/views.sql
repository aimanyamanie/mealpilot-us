-- MealPilot US: database views. Safe to re-run: drops and recreates.
-- (python apply_sql.py views.sql)
--
-- APP-FACING: the contract with the app team. The app reads only these:
--   v_published_recipes   browse, search, recipe detail, guest samples
--   v_plannable_recipes   the plan generator's input
--   v_recipe_ingredients  one recipe's lines, with per-serving amounts
--   v_recipe_steps        one recipe's method, shown steps only
--   v_recipe_flags        allergen and dietary tags, derived from ingredients

DROP VIEW IF EXISTS v_plannable_recipes CASCADE;
DROP VIEW IF EXISTS v_published_recipes CASCADE;
DROP VIEW IF EXISTS v_recipe_steps CASCADE;
DROP VIEW IF EXISTS v_recipe_ingredients CASCADE;
DROP VIEW IF EXISTS v_recipe_flags CASCADE;

-- ---------------------------------------------------------------
-- v_recipe_flags: DERIVED FROM THE MATCHED INGREDIENTS, never from the
-- title. "Chicken" in a title proves nothing about the stock.
--
-- The costs are asymmetric: a false positive hides a recipe someone could
-- have eaten; a false negative serves an allergen to someone who told us not
-- to (TC-16: zero violations). So flags_known is true only when EVERY line
-- matched an ingredient and every such ingredient has had its allergens
-- reviewed. Every is_* tag below is false unless flags_known is true, so a
-- filter on a tag can never pass an unknown recipe.
--
-- halal and kosher are "compatible" only, as far as ingredients can tell:
--   halal_compatible   no pork, no alcohol. Whether the meat must be
--                      certified halal is open with Medina.
--   kosher_style       no pork, no shellfish, and no meat or poultry in the
--                      same recipe as dairy. Not a certification.
-- ---------------------------------------------------------------
CREATE VIEW v_recipe_flags AS
WITH agg AS (
  SELECT r.id AS recipe_id,
         coalesce(bool_or(i.has_milk), false)      AS has_milk,
         coalesce(bool_or(i.has_egg), false)       AS has_egg,
         coalesce(bool_or(i.has_fish), false)      AS has_fish,
         coalesce(bool_or(i.has_shellfish), false) AS has_shellfish,
         coalesce(bool_or(i.has_tree_nut), false)  AS has_tree_nut,
         coalesce(bool_or(i.has_peanut), false)    AS has_peanut,
         coalesce(bool_or(i.has_wheat), false)     AS has_wheat,
         coalesce(bool_or(i.has_soy), false)       AS has_soy,
         coalesce(bool_or(i.has_sesame), false)    AS has_sesame,
         coalesce(bool_or(i.has_gluten), false)    AS has_gluten,
         coalesce(bool_or(i.has_alcohol), false)   AS has_alcohol,
         coalesce(bool_or(i.animal_source = 'pork'), false) AS has_pork,
         coalesce(bool_or(i.animal_source = 'beef'), false) AS has_beef,
         coalesce(bool_or(i.animal_source IN ('pork', 'beef', 'other_meat', 'poultry')), false)
                                                   AS has_meat_or_poultry,
         coalesce(bool_or(i.animal_source IN ('fish', 'shellfish')), false)
                                                   AS has_seafood,
         coalesce(bool_or(i.animal_source = 'other_animal'), false) AS has_other_animal,
         coalesce(bool_or(i.animal_source IS NOT NULL), false)      AS has_animal,
         -- A recipe with no lines gets one all-NULL row from the LEFT JOIN,
         -- which makes this false: no lines is not "allergen-free".
         coalesce(bool_and(ri.ingredient_id IS NOT NULL AND i.allergens_reviewed), false)
                                                   AS flags_known
  FROM recipes r
  LEFT JOIN recipe_ingredients ri ON ri.recipe_id = r.id
  LEFT JOIN ingredients i ON i.id = ri.ingredient_id
  GROUP BY r.id
)
SELECT agg.*,
       flags_known AND NOT (has_meat_or_poultry OR has_seafood OR has_other_animal)
                                            AS is_vegetarian,
       flags_known AND NOT has_animal       AS is_vegan,
       flags_known AND NOT has_gluten       AS is_gluten_free,
       flags_known AND NOT has_milk         AS is_dairy_free,
       flags_known AND NOT has_pork         AS is_no_pork,
       flags_known AND NOT has_beef         AS is_no_beef,
       flags_known AND NOT has_seafood      AS is_no_seafood,
       flags_known AND NOT (has_pork OR has_alcohol)
                                            AS is_halal_compatible,
       flags_known AND NOT (has_pork OR has_shellfish OR (has_meat_or_poultry AND has_milk))
                                            AS is_kosher_style
FROM agg;

-- ---------------------------------------------------------------
-- v_recipe_ingredients: per-serving amounts derived on read. Exact
-- fractions here; the app rounds for display only (US-09: changing
-- servings scales these and leaves per-portion nutrition unchanged).
-- ---------------------------------------------------------------
CREATE VIEW v_recipe_ingredients AS
SELECT ri.id,
       ri.recipe_id,
       ri.display_order,
       ri.group_label,
       ri.raw_text,
       ri.quantity,
       ri.quantity_max,
       ri.quantity / r.source_servings              AS quantity_per_serving,
       ri.quantity_max / r.source_servings          AS quantity_max_per_serving,
       u.slug                                       AS unit,
       u.name                                       AS unit_name,
       u.plural                                     AS unit_plural,
       ri.modifier,
       i.slug                                       AS ingredient,
       i.name                                       AS ingredient_name,
       i.is_divisible,
       i.store_section,
       i.shop_unit,
       i.shop_unit_grams,
       i.price_usd                                  AS shop_unit_price_usd,
       ri.preparation_note,
       ri.is_optional,
       ri.is_scalable,
       ri.grams_as_purchased / r.source_servings    AS grams_as_purchased_per_serving,
       ri.grams_edible / r.source_servings          AS grams_edible_per_serving,
       i.data_quality,
       ri.ingredient_id IS NULL                     AS is_unmatched
FROM recipe_ingredients ri
JOIN recipes r          ON r.id = ri.recipe_id
LEFT JOIN units u       ON u.id = ri.unit_id
LEFT JOIN ingredients i ON i.id = ri.ingredient_id;

-- ---------------------------------------------------------------
-- v_recipe_steps: only steps we wrote. source_text is not exposed.
-- ---------------------------------------------------------------
CREATE VIEW v_recipe_steps AS
SELECT s.recipe_id,
       s.step_number,
       s.instruction,
       s.timer_seconds,
       s.is_hands_off
FROM steps s
WHERE NOT s.needs_rewrite;

-- ---------------------------------------------------------------
-- v_published_recipes: what a user may see. Requires:
--   - status = 'published' and a nutritionist sign-off (PRD, nutrition accuracy)
--   - the creator's permission on file
--   - every nutrition field present (NE-16, TC-19)
--   - at least one step, and no step still awaiting a rewrite
-- video_status is exposed, not filtered: an unavailable video keeps the
-- recipe visible with its written steps (NE-15).
-- ---------------------------------------------------------------
CREATE VIEW v_published_recipes AS
SELECT r.id,
       r.slug,
       r.market,
       r.title,
       r.cuisine,
       r.recipe_type,
       r.meal_slots,
       r.plannable,
       r.is_guest_sample,
       r.video_id,
       r.video_url,
       r.video_duration_seconds,
       r.video_status,
       r.recipe_page_url,
       r.thumbnail_url,
       r.source_servings,
       r.prep_minutes,
       r.cook_minutes,
       r.prep_minutes + r.cook_minutes AS total_minutes,
       r.difficulty,
       r.fridge_days,
       r.freezer_days,
       r.reheat_method,
       r.portion_description,
       c.slug          AS creator_slug,
       c.display_name  AS creator_name,
       c.channel_name  AS creator_channel_name,
       c.channel_url   AS creator_channel_url,
       c.avatar_url    AS creator_avatar_url,
       n.per_serving_kcal,
       n.per_serving_protein,
       n.per_serving_carb,
       n.per_serving_fat,
       n.per_serving_fiber,
       n.per_serving_sugar,
       n.per_serving_sodium_mg,
       n.per_serving_cost_usd,
       n.reference_version,
       f.flags_known,
       f.has_milk, f.has_egg, f.has_fish, f.has_shellfish, f.has_tree_nut,
       f.has_peanut, f.has_wheat, f.has_soy, f.has_sesame, f.has_gluten,
       f.is_vegetarian, f.is_vegan, f.is_gluten_free, f.is_dairy_free,
       f.is_no_pork, f.is_no_beef, f.is_no_seafood,
       f.is_halal_compatible, f.is_kosher_style
FROM recipes r
JOIN creators c         ON c.id = r.creator_id
JOIN recipe_nutrition n ON n.recipe_id = r.id
JOIN v_recipe_flags f   ON f.recipe_id = r.id
WHERE r.status = 'published'
  AND r.nutrition_reviewed_at IS NOT NULL
  AND c.permission_status = 'granted'
  AND n.per_serving_kcal      IS NOT NULL
  AND n.per_serving_protein   IS NOT NULL
  AND n.per_serving_carb      IS NOT NULL
  AND n.per_serving_fat       IS NOT NULL
  AND n.per_serving_fiber     IS NOT NULL
  AND n.per_serving_sugar     IS NOT NULL
  AND n.per_serving_sodium_mg IS NOT NULL
  AND EXISTS (SELECT 1 FROM steps s WHERE s.recipe_id = r.id)
  AND NOT EXISTS (SELECT 1 FROM steps s WHERE s.recipe_id = r.id AND s.needs_rewrite);

-- ---------------------------------------------------------------
-- v_plannable_recipes: the plan generator's input. Meals only, with at
-- least one slot, plus the ingredient ids the generator uses to reward
-- shopping-list overlap.
-- ---------------------------------------------------------------
CREATE VIEW v_plannable_recipes AS
SELECT p.*,
       coalesce(
         (SELECT array_agg(DISTINCT ri.ingredient_id ORDER BY ri.ingredient_id)
          FROM recipe_ingredients ri
          JOIN ingredients i ON i.id = ri.ingredient_id
          WHERE ri.recipe_id = p.id AND NOT i.shopping_exempt),
         ARRAY[]::bigint[]) AS ingredient_ids
FROM v_published_recipes p
WHERE p.plannable
  AND p.recipe_type = 'meal'
  AND p.meal_slots IS NOT NULL
  AND cardinality(p.meal_slots) > 0;
