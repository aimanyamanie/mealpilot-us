# MealPilot US

A rebuild of MealPilot for the US market: a recipe library with calorie and
macro figures we can stand behind, scaled to any portion, feeding a personalised
30-day meal plan and a weekly grocery list.

The first version was built for Indonesia and lives at
`C:\Users\Aiman\OneDrive\Documents\mealpilot-data`
(github.com/aimanyamanie/mealpilot-data): a Python pipeline on Postgres (Neon,
Singapore) that turned Indonesian YouTube recipes into structured data. Read it
for lessons, but do not copy it wholesale; its rules were tuned to Indonesian
food.

## Keep this file short

Claude reads this file at the start of every session. The Indonesian version's
CLAUDE.md grew to 900 KB because every investigation was written up here.
- This file holds **current rules and how to run things**, nothing else.
- Write up investigations, measurements and retracted findings in
  `docs/decisions/YYYY-MM-DD-topic.md`, and add a one-line rule here only if it
  changes how future work should be done.
- When a rule here stops being true, delete it.

## Status

Nothing built yet. See **Open decisions** below.

## Rules carried over from the Indonesian version

These cost real bugs to learn. They still apply.

- **Never publish a number we cannot source.** Every ingredient records
  `nutrition_source`, `source_ref`, `data_quality`
  (`verified` / `researched` / `derived` / `estimated`) and who checked it.
  "We don't know yet" must be representable.
- **Picking the source record is the dangerous step.** A USDA search returns
  several candidates. Read the record's `description` against what the
  ingredient means, then check the macros fit the food. Matching energy values
  prove nothing if the wrong record was copied faithfully (the old project once
  had chicken thigh pointing at "Chicken, skin").
- **Store quantities as the source states them**, plus how many servings that
  makes. Per-portion figures are derived when read, never stored. A wrong
  serving count should be a one-field fix.
- **One master row per real-world ingredient**, with aliases doing the matching
  ("scallion" | "green onion" | "spring onion"). Missing aliases fail silently,
  so treat alias coverage as a measured metric.
- **A line we cannot convert to grams is a failure, not an exemption.** Coverage
  counts every line that states an amount. Below the threshold the recipe is
  held, not shown with a quietly low calorie count.
- **Keep fractions exact in the nutrition math.** Round only for display.
- **Generated counts in docs come from the database**, not from hand edits.

## US-market specifics

- **Units:** recipes use cups, tbsp, tsp, oz, lb, fl oz, sticks of butter, cans,
  and "1 medium onion". Converting volume to grams needs per-ingredient
  densities and piece weights. USDA FoodData Central `foodPortions` covers many
  of these, so cite it instead of guessing.
- **Display:** USD, °F, MM/DD/YYYY, US spelling.
- **Nutrition source:** USDA FoodData Central (Foundation + SR Legacy) is
  primary. It is public domain (CC0), so we can store it. Use Branded Foods
  only for packaged products that are actually used as ingredients.
- **Allergens:** the FDA's 9 major allergens: milk, eggs, fish, crustacean
  shellfish, tree nuts, peanuts, wheat, soybeans, sesame (added 2023 by the
  FASTER Act).
- **Dietary filters US users expect:** vegetarian, vegan, gluten-free,
  dairy-free, low-carb/keto, high-protein. Consider halal and kosher too. From
  the old spec: a plan needs about 40–50 usable recipes per filter combination,
  so don't offer a filter the library can't fill.
- **Regulatory, check before launch:** don't make health or "healthy" claims
  without checking FDA rules. If we store diet, weight or health goals, the FTC
  Health Breach Notification Rule and state consumer-health-data laws
  (Washington's My Health My Data Act, CCPA/CPRA) may apply.
- **Infrastructure:** host the database in a US region.

## Open decisions

Fill these in as they are made, then move each into the right section above.

- [ ] Where recipes come from: US creators (licensing and attribution),
      commissioned recipes, or a mix
- [ ] Product surface: web app, mobile app, or both, and the stack
- [ ] Whether to reuse the old Python pipeline (parser, nutrition engine,
      `meal_planner.py`) or start fresh
- [ ] Database: Postgres on Neon in a US region, or something else
- [ ] Grocery integration (Instacart, Kroger, Walmart), or a plain list for MVP
- [ ] Who is on the team for the US version, and who decides product questions

## How to run

Nothing yet. Add commands here as soon as there is something to run.

## Secrets

`.env` holds credentials and is gitignored. Commit a `.env.example` with
empty values instead.
