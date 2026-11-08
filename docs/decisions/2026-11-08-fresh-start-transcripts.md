# 2026-11-08: Fresh start, recipes from YouTube transcripts

## Decisions (Aiman)
- **Start fresh** rather than restore the Oct 29–30 build. The working folder had
  been emptied; the old files are still in git history (last commit `9193a73`).
- **Transcripts go to `main`.** This reverses the Oct 29 rules that recipe data
  comes only from licensed creator cards and that captions are never fetched.
  Aiman supplies the transcripts.

## What happened to the old database
Nothing was deleted.
- Neon branch `archive-v1-2026-10-30` is a snapshot of `main` before the change.
- On `main`, the old tables and views were moved into schema `archive_v1`
  (248 ingredients, 597 portions, no recipes). The new tables are in `public`.

## The new design
- `schema.sql`: units, USDA nutrients, ingredients (with food group, gluten,
  animal rennet, alcohol), aliases, allergens (FDA 9), per-100 g nutrients,
  household portions, chefs, sources (transcript kept internally), recipes,
  ingredient lines, steps.
- Each line records `quantity_basis` (stated / estimated / to_taste), the
  transcript quote and timestamp it rests on, its grams and how they were found.
- `views.sql` computes everything per serving: all ~146 USDA nutrients
  (`v_recipe_nutrients`), the headline panel (`v_recipe_nutrition`), allergens
  and diet tags (`v_recipe_flags`), and the app's `v_recipe_card`.
- `stated_share` on the card is the share of the recipe's counted grams whose
  amount the creator actually said.

## First recipe: Joshua Weissman, Chicken Alfredo (`6-m_u_8r81o`)
The transcript states only three amounts: 4 cloves garlic, about 1/2 cup
Parmigiano, and 1 lb pasta. Everything else (thighs, cream, butter, oil,
pecorino, seasonings, servings, times) is estimated and listed in the recipe's
`notes`.

Result per serving (4 servings): **1,437 kcal**, 58.8 g protein, 90.7 g carbs,
92.5 g fat (44.3 g saturated), 959 mg sodium. Stated share: 0.28. Allergens:
milk, wheat. Tags: no pork, no beef, no seafood, alcohol-free. Checked by hand:
5,747 kcal for the batch.

Why it's this high, and where the number is soft:
- Chicken is 30% of the calories. USDA's raw "thigh with skin" weighs 193 g; many
  store-bought boneless thighs are 140–170 g.
- Raw skin-on values ignore the fat that renders into the pan.
- The "2 cups cream" amount is a guess; at 1 cup, the figure drops by about 200 kcal per serving.
- Grated cheese uses USDA's packaged grated cup (100 g); fresh gratings are lighter.

Two bad USDA picks were caught by reading the record: 172386 (thigh, *fried,
batter*), and the cream cup that would default to whipped (120 g) without the
`fluid` qualifier.
