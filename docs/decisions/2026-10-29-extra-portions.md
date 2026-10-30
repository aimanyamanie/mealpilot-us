# 2026-10-29: Weights the USDA records lack (extra_portions.csv)

## Why
On the YouTube test branch, the most common matched lines without grams were
weights that our picked USDA records don't publish:

| Line | Lines | Picked record has |
|---|---:|---|
| 1 cup Greek yogurt | 78 (+12 tbsp) | a 6 oz container only |
| 1 shallot | 76 | 1 tbsp chopped only |
| 3 bay leaves | 60 | crumbled tbsp and tsp only |
| 1/2 cup grated pecorino | 36 | oz only |
| 1 cup almond flour | 28 | nothing |
| 1 tbsp chia seeds | 25 | oz only |

Pinch, dash and "to taste" lines were also common, but they never count against
coverage, so they aren't gaps.

## What was built
`pipeline/extra_portions.csv`: one row per weight, with `source` and
`source_ref`. `build_seed.py` adds these to the USDA portions:
- the default and density rules treat them the same way;
- it stops if a row duplicates a USDA portion;
- they need the same human sign-off as every other portion.

`validate_seed.py` now requires every portion to have a source (`USDA`, `LABEL`,
`MEASURED` or `ESTIMATE`) and a `source_ref`.

## Sources, in order of preference
1. **Another USDA record or dataset.** FNDDS (USDA's survey database) has household
   measures that SR Legacy lacks:
   - Greek yogurt: 1 cup = 245 g (FDC 2705424);
   - chia seeds: 1 cup = 168 g (FDC 2707590).
2. **Simple arithmetic on a USDA portion:**
   - brown sugar: 1 tbsp packed = 3 × 1 tsp packed;
   - marinara: 1 cup = 2 × the ½-cup serving;
   - cherry tomatoes: 1 pint = 2 × 1 cup.
3. **A cooked twin of the same food.** Canned chickpeas: 1 cup = 164 g, from cooked
   chickpeas (FDC 173757). Drained, it's the same bean.
4. **A product label from USDA Branded Foods**, for things sold in packages:
   - almond flour: ¼ cup = 28 g;
   - grated pecorino: 1 tbsp = 5 g;
   - shallots: 1 piece = 30 g (Christopher Ranch, matching another brand);
   - bay leaves: 1 leaf = 0.5 g.
5. **Measured** in our own kitchen. Not used yet.

These were looked up through the FDC API with the public `DEMO_KEY`, which ran out
after about a dozen searches. A free FDC API key in `.env` (`FDC_API_KEY`) would
allow the rest.

## Wrong matches fixed at the same time
These lines matched the wrong ingredient. That's worse than no match, because it
would show the wrong food.
- **"bell pepper" matched black pepper:**
  - "bell pepper" with no colour now counts as red (noted on the pick);
  - a new yellow bell pepper ingredient also covers orange, since USDA has no
    orange record. Neither USDA yellow record publishes sugar, so a recipe heavy
    in yellow pepper is held for `no_sugar`.
- **"lemon zest" matched the whole lemon.** It's now its own ingredient (USDA
  lemon peel, 1 tsp = 2 g).
- **"almond milk" matched almonds.** It's now its own ingredient (Foundation
  1999631 for nutrition). Its cup weight comes from SR Legacy: 262 g, which is
  1.11 g/ml and heavy for almond milk. Check it on review.

## Result (test branch, from the database, 2026-10-30)
| | Before | After |
|---|---:|---:|
| Lines with grams (of 22,285) | 16,839 | 17,274 |
| Recipes with ≥90% of lines converted (of 2,187) | 1,117 | 1,300 |
| Usable: servings stated, ≥90% converted, every nutrient | 143 | 159 |

The Mediterranean Dish went from 127 to 171 recipes at ≥90%, but only 6 of its
recipes state servings, so its usable count didn't move. Servings are still the
limit, and only licensed recipe cards fix that.

## Still open
These need a measurement or more lookups:
- a bunch of parsley, cilantro, kale or green onions (about 40 lines);
- a head of garlic (14);
- a sprig of rosemary or thyme (34). "rosemary" also matches the dried herb even
  when the line says sprig.

Wrong matches still to fix:
- almond extract matches almonds (USDA has no almond extract record);
- vanilla protein powder matches vanilla extract;
- "1/8th teaspoon", "TBPS", "C." and "of a cup" aren't read as units.
