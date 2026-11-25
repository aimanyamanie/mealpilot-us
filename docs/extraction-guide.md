# MealPilot US: drafting a recipe from a Joshua Weissman transcript

You turn one YouTube transcript into one or more recipe files for the MealPilot
US catalogue. Accuracy beats speed: every amount must be traceable, and every
guess must be written down. Work only in `/home/claude/mp`. Never edit files
another helper owns. Don't touch any database.

## Files

- `data/transcripts/<video_id>.json`: TranscriptAPI output (`transcript[]` of
  `{text, start, duration}`). This is your only source for what he says.
- `recipes/*.json`: three finished examples. Copy their shape exactly.
  `chorizo-breakfast-burrito-joshua-weissman.json` is the closest to typical.
- `ingredients.csv`: ingredient slugs that already exist. Reuse them, matching
  on `aliases`.
- `units.csv`: the only allowed `unit` codes.
- `finalize.py`: fills timestamps and checks a draft. Run it until it is clean.

## Steps for each video

1. Read the whole transcript.
2. Decide how many recipes it holds (see "Several versions" below).
3. Find the written recipe on joshuaweissman.com. Use WebSearch, e.g.
   `joshuaweissman.com <dish>`, then WebFetch the page. Use it for servings,
   times, and any amount the transcript leaves unclear or garbled. If there is
   no written recipe, say so in `notes`.
4. Write `drafts/<slug>.json`. Each ingredient line gets a `th` field with the
   approximate second where the evidence is spoken; finalize turns it into `t`.
5. Put any ingredient that isn't in `ingredients.csv` in
   `drafts/new_<your helper id>.csv`, with the columns
   `slug,name,usda_search,note`:
   - `slug`: kebab-case, generic (`buttermilk`, `panko`, `chicken-wing`).
   - `usda_search`: 2–5 words to search USDA SR Legacy, e.g. `buttermilk lowfat cultured`.
   - `note`: anything that matters for picking the record, e.g. raw vs cooked,
     a brand-like item, a proxy.
6. Run `python3 finalize.py drafts/<slug>.json`. Fix every `!` line. Check
   every `~` line too, and add a `th` where the evidence occurs more than once.

## Recipe fields

- `slug`: `<dish>-joshua-weissman`, lowercase kebab-case. For versions, add a
  suffix such as `-level-1`, `-easy` or `-buffalo`.
- `market`: `"US"`.
- `title`: our own short title.
- `summary`: 1–2 sentences in our own words.
- `chef`: copy it exactly from an example file. It uses the main channel ID on
  purpose.
- `source`: `{"kind": "youtube_transcript", "transcript_file": "data/transcripts/<id>.json"}`.
- `cuisine`.
- `course`: one of `breakfast | main | side | snack | dessert | drink | component`.
- `meal_slots`: a subset of `breakfast, lunch, dinner, snack`.
- `servings` and `servings_basis` (`stated | estimated`): stated means he or
  his written recipe gives it.
- `prep_minutes`, `cook_minutes` and `times_basis`: leave them null if
  nothing supports them.
- `difficulty`: `easy | medium | hard`.
- `extracted_by`: `"Claude (Opus 5.5), from the transcript"`.
- `notes`: plain prose. Start with: `Video: '<exact video title>' on the
  Joshua Weissman Recipes channel (UCUAg71CJEvFdOnujmep1Svw).` Then add the
  written recipe URL and what it says about servings and time. Then record
  every guess, range, proxy and exclusion, with the reason.
- `ingredients`: the lines described below.
- `steps`: `[{"t": <seconds>, "text": "<our own words>"}]`. Paraphrase.
  Never copy his sentences.

## Ingredient lines

`{"group", "ingredient", "text", "quantity", "unit", "qualifier"?, "preparation"?,
"basis", "evidence", "th", "in_nutrition"?, "excluded_reason"?,
"amount_source"?, "amount_url"?, "amount_note"?}`

- **`quantity`:** a number or a fraction string, like `"1 1/2"` or `"1/4"`.
  Use null only for `to_taste` lines.
- **`unit`:** must exist in `units.csv`. Use null for a bare count, like
  "2 eggs". For a whole countable item, use `whole`, or a size (`large`,
  `medium`, `small`) when he says one. If nothing fits, convert to `g` and
  explain how in `amount_note`, and if it's our conversion also set
  `basis: estimated` with `amount_source: our_estimate`.
- **`basis`:**
  - `stated`: he gives the amount for this dish, in the video or in the written recipe.
  - `estimated`: we picked the number.
  - `to_taste`: no amount. Always set `in_nutrition: false` with
    `excluded_reason: "amount not stated"`, unless the house rules below say
    to count it.
- **`amount_source`:**
  - Omit it for stated amounts from the transcript.
  - `creator_recipe`: the amount came from the written recipe. Requires
    `amount_url` and `amount_note`. The transcript wins wherever it states an
    amount.
  - `our_estimate`: estimated by us. This is the default for `estimated`, so
    you may omit it.
- **`evidence`:** the exact words from the transcript, lowercase is fine.
  Joining pieces with `...` is allowed: every piece must appear within 20 s
  of the first. Quote where he names the ingredient, even if the amount came
  from the website. Caption errors must be quoted as they appear in the
  captions ("tepoon"). Do not correct them.
- **Not eaten, or not countable:** set `in_nutrition: false` and a short
  `excluded_reason`.

## House rules (Aiman's decisions)

1. **Sauces:** a sauce drizzled or tossed on the dish counts. A sauce served
   on the side for dipping is excluded, with the reason "served on the side".
   A recipe whose whole point is the sauce (a component) counts it, of course.
2. **Deep-frying oil:** the oil filling the pot is excluded, with the reason
   "frying oil; absorbed oil counted separately". Add one extra line for the
   absorbed oil:
   - Use the same oil slug.
   - Set `text: "Absorbed frying oil (our estimate)"`.
   - Use `quantity` in `g` equal to 10% of the raw weight of the fried food
     (with its coating).
   - Set `basis: estimated`, `amount_source: our_estimate`.
   - Quote the oil mention as `evidence`.
   - Show the arithmetic in `amount_note`.
   Shallow pan oil that stays with the food is counted as stated.
3. **Coatings:** count 25% of a dry dredge (flour, starch, breadcrumbs, panko,
   seasoned flour mix) and 50% of a wet batter. Use one line per ingredient at
   the counted amount:
   - Set `basis: estimated`, `amount_source: our_estimate`.
   - Set `amount_note`, e.g. "2 cups stated; 25% counted as dredge that sticks
     (house rule)".
   - Keep the stated amount in `text`.

   Egg washes count at 50%. Liquid marinades and brines that are poured off are
   excluded. Thick marinades that stay on the meat, like yogurt or paste, count
   in full.
4. **Salt:** a small salt amount that we estimate is counted. Salt in
   pasta-cooking water is excluded.
5. **Proxies:** if no close ingredient exists, propose the nearest USDA food as
   a new slug and name the proxy in `note` and in the recipe `notes`.
6. **Several versions in one video** ("2 Ways", "3 Levels", "3 Lazy Pasta",
   sauce roundups): write one recipe file per version, all pointing to the same
   transcript. Shared base lines are repeated in each file. If a version has no
   real amounts at all, still write it, with estimates, and say so.
7. **Components:** for stocks, butter, flavored oils, sauces, dressings,
   toppings and pickles, set `course: "component"` and `meal_slots: []`.
   Breads that are only used inside other dishes, like burger buns, are also
   components. Bagels, focaccia and biscuits are not; give them meal slots.
8. **Garnish with no amount:** exclude it. A garnish with an amount counts.
9. **Optional or alternative ingredients:** count the first-named option.
   Exclude the alternatives, with the reason "alternative".

## Report back (keep it short)

For each recipe:
- its slug
- whether finalize is clean
- servings, and whether stated or estimated
- every judgment call in one line each: ranges, proxies, website-sourced amounts, versions

Then list the paths of your new-ingredient CSVs.

## House rules added 2026-11-24 (apply to all batches)

10. **Sauce or spice oil made in a bigger batch than goes on the food**
    (tossed wing sauce, glaze, brushed or dunked hot oil, chili oil):
    - If he or the written recipe says the share used (for example "makes
      enough for 4 lb, we use 2 lb"), count that share.
    - Otherwise count 50% of a tossed sauce or glaze, and 25% of a brushed or
      dunked spice oil.
    - Set `basis: estimated`, `amount_source: our_estimate`, and show the share
      in `amount_note`. Keep the full batch amount in `text`.
    - A sauce made for the dish and fully used (spread, simmered in) counts in full.
11. **Optional ingredients:** count one only if he actually adds it in the
    video. If he only mentions it, set `in_nutrition: false` with
    `excluded_reason: "optional, not added in the video"`. Optional alcohol is
    always excluded (`"optional alcohol"`), with a note.
12. **Bone-in chicken:** enter the as-bought weight with bone, exactly as
    stated (e.g. `2` `lb`), use the bone-in slug (`chicken-wing`,
    `chicken-leg-quarter`, `chicken-thigh-bone-in`, `chicken-whole`,
    `chicken-drumstick`), and write `"as bought, bone-in"` in `amount_note`.
    Do not subtract bone yourself: the lead converts it to edible weight with
    USDA's own yield for that cut. Absorbed-oil arithmetic uses the as-bought
    weight.
13. **Times:** `prep_minutes` is hands-on prep. Put marinating, brining and
    resting time in `notes`, not in `prep_minutes`.
