# 2026-11-16: Where each ingredient amount comes from

## Decisions (Aiman)
1. **Transcript first, written recipe second.** Amounts come from the transcript.
   Where the transcript is unclear, the creator's written recipe is the
   reference. The source of every amount is recorded per ingredient.
2. **Chicken Alfredo follows the website ratio** for the amounts the video
   leaves out.
3. **Recipes with a low `stated_share` may be published.**

## Schema (migration `2026-11-16-amount-source.sql`)
`recipe_ingredients` gains:
- `amount_source`: `transcript`, `creator_recipe` or `our_estimate`
  (null only for `to_taste`).
- `amount_source_url`: the written recipe page; required exactly when the
  source is `creator_recipe`.
- `amount_note`: which recipe and how it was scaled; required for
  `creator_recipe`.

`quantity_basis` keeps its meaning: `stated` means the creator gave the amount
for this dish, whether in the video or in a written recipe for the same dish.
The 16 existing lines were backfilled from their basis (stated → transcript,
estimated → our_estimate). `stated_share` and the app views are unchanged.

## Chicken Alfredo (`6-m_u_8r81o`)
The video says "recipe on the website", and its description's "Full Recipe" link
is https://www.joshuaweissman.com/post/perfect-fettuccine-alfredo, "Making The
Perfect Fettuccine Alfredo (3 Ways)". It has no chicken. Its American Fettuccine
Alfredo: 14 oz (400 g) dried fettuccine, 1.25 cups (300 ml) heavy whipping cream,
1/2 cup (115 g) unsalted butter, 2 cups (250 g) Parmesan, 2 tsp finely chopped
thyme, 5 cloves garlic, pepper to taste; serves 3. A search of
joshuaweissman.com for "alfredo" and "faster" (2026-11-15) found no chicken
alfredo recipe.

That page is a different version (Parmesan only, more garlic, less pasta), so its
numbers are used only where the video gives none, scaled by 8/7 to the video's
stated 1 lb pasta, and the lines stay `estimated`:

| Line | Before | After | Source |
|---|---|---|---|
| Heavy cream | 2 cups (our estimate) | 1 1/2 cups (1.43 scaled) | creator_recipe |
| Unsalted butter | 2 tbsp (our estimate) | 9 tbsp (9.14 scaled) | creator_recipe |
| Fresh thyme | 1 tsp (our estimate) | 2 1/4 tsp (2.29 scaled) | creator_recipe |

Garlic (4 cloves), Parmigiano (about 1/2 cup) and pasta (1 lb) stay as the video
states them. Chicken, oil, pecorino and seasonings stay our estimates; the page
has none of them.
