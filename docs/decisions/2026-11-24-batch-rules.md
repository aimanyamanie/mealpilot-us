# 2026-11-24: extraction house rules for the full Weissman catalogue

Decided by Aiman while loading batches 1–2 (Joshua Weissman Recipes channel).
The full rules for drafting a recipe are in `docs/extraction-guide.md`. This
file records the decisions and why.

## Counting rules

1. **Sauces.** A sauce drizzled or tossed on the dish counts. A sauce served on the
   side for dipping is excluded ("served on the side").
2. **Deep-frying oil.** The oil in the pot is excluded. Absorbed oil is counted
   as 10% of the raw weight of the fried food, coating included (our estimate;
   `amount_source = our_estimate`). Batch 1 originally excluded frying oil;
   the hash browns (breakfast burrito) and crispy eggs (nasi goreng) were
   updated to this rule.
3. **Coatings.** Count 25% of a dry dredge, 50% of a wet batter, and 50% of an
   egg wash. Liquid marinades and brines that are poured off are excluded.
   Thick marinades that stay on the meat count in full.
4. **Batch sauces and spice oils** (made in more than goes on the food):
   - If he states a share, count that share.
   - Otherwise count 50% of a tossed sauce, and 25% of a brushed or dunked spice oil.
5. **Optional ingredients** count only if he adds them in the video.
   Optional alcohol is never counted.
6. **Small estimated salt** amounts count. Salt in pasta-cooking water does not.
7. **Proxies** are allowed when USDA has no record; each is named in the
   ingredient's `pick_note` and in the recipe notes.
8. **Versions.** One recipe per version ("2 Ways", "3 Levels"). The versions
   share the same transcript.
9. **Components** (stock, butter, oils, sauces, dressings, toppings, buns) use
   `course = 'component'` and empty `meal_slots`, so the planner never offers
   them as meals. Migration `2026-11-24-component-course.sql`.
10. **Times.** `prep_minutes` is hands-on time only. Marinating and resting go
    in the notes.

## Weights

- **Bone-in chicken** is entered as edible weight: the as-bought weight less
  USDA's bone percentage for that cut (SR28 report for food group 05). Each
  line keeps the as-bought amount in `text` and the arithmetic in `amount_note`.

  | Cut | Bone removed | USDA source |
  |---|---|---|
  | Wing | 38% (bone and connective tissue) | NDB 05100 |
  | Leg quarter | 27% | NDB 05075 |
  | Whole broiler, meat and skin | 32% | NDB 05006 |
  | Thigh | 19% | NDB 05092, the fried thigh. The raw thigh record, 05091, prints 0% (boneless sample). |

- **Fresno / red jalapeño chili:** 1 pepper = 14 g (USDA jalapeño 168576), set in
  `extra_portions.csv`. The generic red chili record weighs 45 g per pepper.
- **Branded records** (MSG, sambal, panko, potato starch, rice syrup, sorrel
  drink) have no household portions. Their spoon or cup weights come from the
  product label, or from Josh's own written recipe for MSG (3 g per tsp), and
  are entered in `extra_portions.csv`.

## Loader change

`measures.resolve_grams` now prefers an exact qualifier match over a substring
match. Before, `packed` also matched `unpacked` for brown sugar.
Test: `test_exact_qualifier_beats_substring`.
