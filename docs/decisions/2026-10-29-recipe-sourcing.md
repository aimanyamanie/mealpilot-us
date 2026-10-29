# Recipe sourcing: YouTube API terms and creator shortlist

Date: 2026-10-29
Status: research, input to the open decision "Where recipes come from" in `CLAUDE.md`.
This is a summary for planning, **not legal advice**. Items that need a lawyer are
listed in section 3.

## Recommendation

1. **Don't build ingestion as "YouTube Data API → store descriptions → parse →
   keep the ingredients for good."** The YouTube Developer Policies cap how long
   we may keep data fetched without a user login at 30 days (III.E.4.d). They
   also forbid using API data to create "new or derived data" (III.E.4.h). A
   permanent ingredient and nutrition table parsed from API-fetched descriptions
   is a derived dataset. A refresh job fixes the 30-day problem but not the
   derived-data problem.
2. **Get recipe data from the creator under a written licence, not from the
   API.** Every shortlisted creator already publishes a structured recipe card
   (schema.org `Recipe`, mostly WP Recipe Maker) with servings, quantities and
   their own calorie figure. Ask for an export of those cards, or written
   permission to read them. Data the creator hands us is not "API Data", so the
   YouTube retention and derived-data rules don't apply to it. We still
   recompute nutrition from USDA, per the project rules.
3. **Use the YouTube API only for what it is for:** the embedded player, plus
   display metadata (title, thumbnail, availability) keyed by video ID and
   refreshed at least every 30 days. The refresh also tells us when a video is
   deleted or made private.
4. **Approach five creators first:** Clean & Delicious, Feelgoodfoodie,
   Downshiftology, Sip and Feast and The Protein Chef. For vegetarian depth, add
   The Mediterranean Dish or Vegan Richa. All are US-based channels that link
   every video to a recipe card with servings. Our open filter set needs about
   40–50 usable recipes per filter combination, and five or six back catalogues
   of hundreds of recipes each should reach that. Measure it once we have the
   data.
5. **Pay for a lawyer's review before signing the first creator.** Have them
   cover the licence template and the questions in section 3.

---

## 1. YouTube API terms

Pages read on 2026-10-29:

- [YouTube API Services – Developer Policies](https://developers.google.com/youtube/terms/developer-policies), last updated 2026-10-15
- [YouTube API Services – Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service), last updated 2026-09-14
- [Complying with YouTube's Developer Policies](https://developers.google.com/youtube/terms/developer-policies-guide) (Google's guide), last updated 2026-09-14
- [Required Minimum Functionality](https://developers.google.com/youtube/terms/required-minimum-functionality), last updated 2026-10-15
- [YouTube Terms of Service](https://www.youtube.com/t/terms) (the general site terms)

Clauses below are cited by section number and heading and paraphrased. Check
the live pages before relying on any wording, because Google revises these
pages often (two of them changed this month).

### 1.1 Storing API data (descriptions, titles, IDs)

Definitions: **Non-Authorized Data** is API Data an API client can get without
user credentials. Video descriptions fetched with an API key fall in this group.
**Authorized Data** is data a signed-in user lets us access. We would have none
of it.

| Clause | What it says (paraphrased) |
|---|---|
| III.E *Handling YouTube Data and Content*, preamble | Beyond what section III.E grants, we have no rights to API Data, including data we store temporarily. |
| III.E.4 *Refreshing, Storing, and Displaying API Data*, (d) | We may temporarily store limited amounts of Non-Authorized Data for as long as the client needs it, but **not longer than 30 calendar days**. |
| III.E.4 (c) | Authorized Data: at most 30 days, then delete or refresh. Not relevant to us. |
| III.E.4 (e), (f) | Stored data must be kept reasonably consistent with YouTube's current data, and we must display the most up-to-date version. |
| III.E.4 (h) | We must not replace API Data with independently calculated substitutes, or **use API Data to create new or derived data or metrics**. This applies to all developers. The exception in III.L covers only audited analytics developers who applied for it. |
| III.E.2 *Data Aggregation* | We may aggregate API Data only for channels under the same content owner, and only that owner may see the result. A cross-creator library built from API data is arguably aggregation. |
| III.E.6 *Scraping* | No scraping of YouTube. The pipeline cannot fall back to reading watch pages. |
| ToS §6 *API Clients and Monitoring* | YouTube may audit our use at any time without notice. |
| ToS §15 *Usage and Quotas* | We must stay within quota. A quota increase above the default triggers a compliance audit, which is where a storage design like ours would be examined. |
| ToS §24.3 *Effect of Termination* | If access is terminated, we must delete all API Data. Any ingredient table derived from it would be exposed. |

**Video IDs.** Neither the Developer Policies nor the guide publish an
exemption for video or channel IDs. Developers commonly treat IDs as storable,
but the text does not say so. In practice we need the ID to embed the video;
see question 2 in section 3.

What this means for each thing we'd store:

| What we'd store | Position if it came from the YouTube API |
|---|---|
| Raw description text | Allowed for up to 30 days, then delete or refresh |
| Title, thumbnail, channel name for display | Allowed for up to 30 days, then refresh. Display them unaltered (developer policies guide) |
| Parsed ingredient lines, quantities, servings | Likely "derived data" (III.E.4.h): not safe to keep permanently on the API's terms alone |
| Our nutrition figures computed from those lines | Same problem, because they are derived from the above |
| Video ID | No explicit exemption; low practical risk; needed for embeds |
| The same facts **supplied by the creator** | Not API Data. Governed by our licence with the creator, not YouTube's terms |

### 1.2 Embedding videos

The embedded player is part of the "YouTube API Services", so the API Terms
and Developer Policies apply to embeds as well.

- **RMF, *Embedded YouTube Player size*:** the player viewport must be at least
  200×200 px, and Google recommends at least 480×270 for 16:9.
- **RMF, *Autoplay and scripted playbacks*:** autoplay may start only when more
  than half the player is visible, and only one autoplaying player per page.
- **RMF, *Overlays and frames*:** nothing may cover the player or its controls.
- **RMF, *API Client Identity and Credentials*:** embeds must send an HTTP
  Referer that identifies our app. Google recommends the
  `strict-origin-when-cross-origin` policy.
- **III.I.4 and III.I.6:** we must not modify, build on, or block the player,
  or remove links in it.
- **III.F.2.c:** we must not obscure YouTube attribution.
- **III.F.3.a:** we must not charge users to watch content in an embedded
  player. **This matters if MealPilot is a paid subscription.** Keep recipe
  pages with embeds outside the paywall, or get advice on whether a subscription
  for meal planning counts (section 3).
- **III.G.1.d:** ads on a page that shows API Data are allowed only when the
  page has enough independent value. Our nutrition and meal-plan features
  should qualify.
- **III.E.4.i and III.E.4.j:** the embed sends data to YouTube on load, and
  turning autoplay off limits what is shared before the user interacts. For
  videos marked Made for Kids, tracking must be off.
  **Practical point:** don't place embeds on pages that also show a user's
  weight, diet or health goals. The health-data laws noted in `CLAUDE.md`
  make that third-party data flow a liability.

### 1.3 Using channel content to build a derived product

- **III.E.4.h and III.E.2** (above) are the main obstacles to building our
  library *from API data*.
- **III.I.1:** we must not replicate YouTube's core experience without
  significant independent value. A meal planner is not a substitute for
  YouTube, so this is low risk.
- **ToS §12 *Third-Party Rights* and §16.3:** API access gives us no licence to
  creators' content. We must not infringe their rights, and the API grants no
  right to reproduce audiovisual content.
- **YouTube Terms of Service:** automated access (scraping) is forbidden except
  as YouTube allows. Note that the research for this doc read a few hundred
  public channel and watch pages once, by hand-run script. The product must
  never do this.

### 1.4 Options for compliance

From most to least recommended:

| Option | How it works | Fit |
|---|---|---|
| **A. Creator supplies recipe data** | The creator exports recipe cards (WP Recipe Maker can export JSON) or fills in a template: title, ingredient lines, servings, video ID. We parse, match to USDA and store permanently under the licence. | **Best.** No YouTube data-retention issue, and we get the servings field, which descriptions rarely have (section 2). The creator keeps control of the method text. |
| **B. Written permission to read their recipe pages** | Same data, but we fetch it from the creator's site under a licence that names this use. | Good. Several creator sites block automated fetches (Cloudflare challenges on sipandfeast.com, feelgoodfoodie.net, budgetbytes.com and others), so we'd need them to whitelist us or give us a feed anyway. |
| **C. Video ID + refreshed display metadata** | Store the video ID permanently. Store title and thumbnail from `videos.list` and refresh them at least every 30 days. Use the same call to detect deleted or private videos and hide those recipes. | **Do this alongside A or B.** Quota cost is trivial: one `videos.list` call covers 50 IDs for 1 unit, and the default quota is 10,000 units a day. |
| **D. Store only parsed facts + video ID, sourced from the API** | Parse descriptions on fetch, keep the facts, drop the text after 30 days. | **Not recommended on its own.** It meets III.E.4.d but is still "derived data" under III.E.4.h. Even with creator permission, YouTube's terms bind us, not the creator, so get advice before relying on it. |
| **E. Refresh jobs on raw descriptions** | Keep the description no more than 30 days and re-fetch on a schedule. | Compliant for the text itself, but we may keep nothing derived. Useful only as a change detector that flags when a creator edits a recipe. |
| **F. Editorial entry** | A person watches the video and types the ingredient list. | Ingredient facts aren't copyrightable (1.5) and this isn't API Data, but it is slow and adds transcription error. We still need the creator's permission to use their name and brand. Fallback only. |

### 1.5 US copyright: ingredient lists vs. method text

- **US Copyright Office, [Circular 33 *Works Not Protected by Copyright*](https://www.copyright.gov/circs/circ33.pdf), "Recipes":**
  "A mere listing of ingredients or contents, or a simple set of directions, is
  uncopyrightable." A registration can cover the written explanation and owned
  photographs, "However, the registration will not cover the list of
  ingredients that appear in each recipe, the underlying process for making
  the dish, or the resulting dish itself." (US government work, public domain.)
- **[*Publications International, Ltd. v. Meredith Corp.*, 88 F.3d 473 (7th Cir. 1996)](https://law.justia.com/cases/federal/appellate-courts/F3/88/473/486900/):**
  a functional list of ingredients is not original under the Copyright Act. A
  compilation copyright in a cookbook does not extend to the facts inside it.
  Directions with expressive elaboration can be protected. Later cases
  followed it, for example *Lambing v. Godiva Chocolatier* (6th Cir. 1998) and
  *Harrell v. St. John* (S.D. Miss. 2011). See the
  [Bradley summary](https://www.bradley.com/-/media/files/insights/publications/2019/07/intellectual-property-protection-for-recipes.pdf).

What this means for us:

- **Ingredient names, quantities and servings are facts.** Copyright alone does
  not stop us storing them.
- **Method text, headnotes, photos and the video are protected.** Our rule of
  never displaying the creator's prose is correct. Store parsed facts, not the
  description or method text.
- **Wholesale copying of a whole catalogue** may touch a thin compilation
  copyright in the selection and arrangement. Licensing removes the question.
- **Contracts can forbid what copyright allows.** YouTube's terms bind us as an
  API client. Creator websites carry their own terms. For example, Raptive (the
  ad network behind many food blogs, including Clean & Delicious) adds
  [*Terms of Content Use*](https://help.raptive.com/hc/en-us/articles/38873087079323-What-are-Terms-of-Content-Use)
  to its sites by default, aimed at scraping and replication
  ([press coverage](https://www.netinfluencer.com/raptive-launches-framework-to-shield-creators-from-ai-scraping/)).
- **Names, faces and brands are a separate issue.** Showing "Recipe by Dani
  Spies" with her photo in the app or in ads raises right-of-publicity and
  false-endorsement questions. Get it in the licence.
- **The creator's own calorie figures** come from the creator's recipe card,
  not USDA. Don't copy them; compute our own from USDA per the project rules.
  They are useful as a cross-check during verification.

---

## 2. Creator shortlist

### Method

- **Description sample:** read the descriptions of each channel's 10 most
  recent long-form uploads on 2026-10-29 and counted:
  - **Inline list:** descriptions with a full inline ingredient list, meaning
    six or more lines that start with a quantity and unit.
  - **Servings inline:** descriptions with a numeric servings statement.
  - Descriptions that link to the creator's own recipe page.
- **Recipe card:** opened one linked recipe page per creator and read its
  schema.org `Recipe` data (`recipeYield`, `calories`).
- **Subscriber counts:** as YouTube displayed them on 2026-10-29, rounded by
  YouTube.
- **Country:** the country listed on each channel's About page.
- **Partnership signals:** from web search. Treat them as leads to confirm on a
  call, not established facts.

Ten videos is a small sample, and recent uploads skew seasonal (fall baking).
Measure again from a channel's full back catalogue before committing to it.

### Ranked for MVP fit

Ranking weighs four things: healthy or weeknight focus that matches our
calorie-targeted plans, structured servings data, no competing meal-plan
product, and likely openness to a licence.

| # | Creator (channel) | Subs | Inline list (of 10) | Servings | Typical cuisine | Licensing / partnership signals |
|---|---|---|---|---|---|---|
| 1 | **Clean & Delicious** (Dani Spies) [@CleanandDeliciousDani](https://www.youtube.com/@CleanandDeliciousDani) | 2.43M | 5; 10/10 link to recipe | Card: yes (lasagna soup: 8 servings, 338 kcal). Inline: 2/10 | Healthy American, high-protein, weight-loss for women 40+ | DK cookbook (2023); on Raptive; [editorial policy](https://cleananddelicious.com/editorial-policies/) limits collaborations to brands that fit her goals. Sells a "Protein PlayBook" lead magnet, not a meal-plan app. **Audience overlaps ours closely.** |
| 2 | **Feelgoodfoodie** (Yumna Jawad) [@Feelgoodfoodie](https://www.youtube.com/@Feelgoodfoodie) | 1.68M | 4; 10/10 link | Card: yes (8 servings, 182 kcal). Inline: 0/10 | Healthy American and Middle Eastern (Lebanese), lots of vegetarian | Penguin Random House cookbook author; brand deals (Home Chef, Stonyfield, Daisy, per [SponsorRadar](https://sponsorradar.com/channels/feelgoodfoodie)); own product Oath Oats; FEELGOODFOODIE trademark. Commercially experienced, so expect a proper negotiation. Check halal suitability recipe by recipe; don't assume it. |
| 3 | **Downshiftology** (Lisa Bryan) [@Downshiftology](https://www.youtube.com/@Downshiftology) | 2.73M | 0; 10/10 link | Card: yes (Greek baked cod: 4 servings) | Healthy, gluten-free, meal prep | Clarkson Potter cookbook *Healthy Meal Prep*. No paid meal-plan product found. Strong gluten-free filter coverage. |
| 4 | **Sip and Feast** (James Delmage, Tara Boerum) [@SipandFeast](https://www.youtube.com/@SipandFeast) | 1.2M | **10**; 10/10 link | Card: yes (chicken orzo: 4 servings, 951 kcal). Inline: 0/10 | Italian-American weeknight and Sunday dinners | Self-published cookbook (Sip and Feast Inc., Nov 2025); Patreon. Independent and small, so likely quick to decide. **Best inline data**, with grams alongside cups. Less "healthy", but strong for weeknight dinners. |
| 5 | **The Protein Chef** (Derek Howes) [@TheProteinChef](https://www.youtube.com/@TheProteinChef) | 524K | 0; 10/10 link | Card: yes (enchilada soup: 8 bowls, 370 kcal) | High-protein American, meal prep, protein desserts | Cookbook *The Protein Blueprint*. Covers the **high-protein** filter. |
| 6 | **The Mediterranean Dish** (Suzy Karadsheh) [@TheMediterraneanDish](https://www.youtube.com/@TheMediterraneanDish) | 659K | 1; 10/10 link | Card: yes (cabbage soup: 6 servings) | Mediterranean, many vegetarian and legume dishes | Penguin Random House cookbooks; free email meal plans (adjacent, but not a paid product). Run as a company with staff and careers page, so licensing would be a business deal. |
| 7 | **Vegan Richa** (Richa Hingle) [@VeganRichaRecipes](https://www.youtube.com/@VeganRichaRecipes) | 70.8K | 0; 10/10 link | Card: yes (harira: 3 servings, 422 kcal). Inline: 5/10 | Vegan, Indian, high-protein plant-based | Cookbook author. Small YouTube channel but a large blog. **Vegetarian/vegan coverage** with protein focus. |
| 8 | **Natasha's Kitchen** (Natasha Kravchuk) [@NatashasKitchen](https://www.youtube.com/@NatashasKitchen) | 4.14M | 1; 9/10 link | Card: yes (lasagna: 10 servings, 435 kcal). Inline: 3/10 | American comfort food, Eastern European, baking | NYT-bestselling cookbook (2023); ["Work With Us"](https://natashaskitchen.com/?p=37746) page offers sponsored posts and ambassadorships. Biggest reach, weakest "healthy" fit. |
| 9 | **Budget Bytes** (Beth Moncel) [@BudgetBytesBlog](https://www.youtube.com/@BudgetBytesBlog) | 43.5K | 0; 10/10 link | Card: yes (8 servings, 289 kcal, plus **cost per serving**) | Budget American, many vegetarian | **Competitor:** BudgetBytes+ membership sells weekly meal plans and grocery lists. Small YouTube channel; the blog is the asset. |
| 10 | **Rainbow Plant Life** (Nisha Vora) [@RainbowPlantLife](https://www.youtube.com/@RainbowPlantLife) | 1.56M | 0; 10/10 link | Card: yes (4 servings, 411 kcal) | Vegan, global (Indian, East Asian) | **Competitor:** paid meal-plan subscription with grocery lists since 2024. Also an NYT Cooking contributor since 2025 (self-reported). Best vegan content, hardest to license. |
| 11 | **Stealth Health Life** (Tom Walsh) [@stealth_health_life](https://www.youtube.com/@stealth_health_life) | 275K | 1 of 1 long-form video | Inline: yes, with servings and per-serving macros | High-protein meal prep, freezer meals | No country listed. Shorts-first: 1 long-form video against roughly 48 Shorts on the channel page. Sells cookbooks and a paid Substack; did product development for COUNTER frozen meals ([his account](https://stealthhealthlife.substack.com/p/the-stealth-health-x-counter-story)). Ideal data shape, but commercially conflicted. |
| 12 | **MyHealthyDish** (My Nguyen) [@MyHealthyDish](https://www.youtube.com/@MyHealthyDish) | 3.02M | 7; 0/10 link | No servings anywhere in the sample | Vietnamese-American, Asian-American family cooking | Penguin Random House cookbooks. Current uploads are a family show ("My Daughters Cooked"). Has inline lists but no servings, which is a blocker under our store-servings rule. |

**Vegetarian coverage:** Vegan Richa and Rainbow Plant Life (fully vegan), plus
large vegetarian shares at The Mediterranean Dish, Feelgoodfoodie and Budget
Bytes.

**High-protein:** The Protein Chef, Clean & Delicious, Stealth Health Life,
plus Vegan Richa for plant protein.

**Gluten-free:** Downshiftology.

### Looked at and not shortlisted

| Channel | Subs | Why not |
|---|---|---|
| Ethan Chlebowski | 2.45M | **Competitor:** his descriptions link recipes to his own Cookwell app (app.cookwell.com). |
| Fit Men Cook (Kevin Curry) | 671K | Recent uploads are entertainment and hacks; sells own seasoning products. |
| Food Wishes (Chef John) | 4.71M | Recipes are hosted on Allrecipes, which [acquired Food Wishes in 2011](https://www.prnewswire.com/news-releases/allrecipescom-acquires-food-wishes-in-major-push-to-dominate-the-online-food-video-space-127301528.html). A licence would go through Allrecipes' owner, not the creator. |
| Joshua Weissman | 10.8M (main), 909K (recipes channel) | Main channel is entertainment; recipes channel links to his site. Indulgent, not weeknight-healthy. |
| Brian Lagerstrom | 1.8M | Inline lists in 5/10, no servings inline; technique-led, not health-led. **Alternate** for weeknight dinners. |
| Laura in the Kitchen | 3.97M | Inline lists in 7/10, but no per-recipe page links and no servings. Comfort and baking. |
| Preppy Kitchen | 6.26M | Mostly baking and desserts. |
| Chef Jean-Pierre | 2.48M | Links to recipe pages, but rich French and Italian food; poor fit for calorie targets. |
| Remington James | 734K | High-protein, but no inline lists; recipes sold as paid e-books. |
| Alyssia Sheikh (formerly Mind Over Munch) | 968K | Channel has become a podcast. |
| The Golden Balance | 3.59M | Entertainment format. |
| The Korean Vegan, Sweet Simple Vegan, HealthyGirl Kitchen, Toni Okamoto | 14K–1.4M | Storytelling or vlogs, or very small YouTube channels. |

### Takeaways for ingestion design

- **Servings are almost never in the description:** 0–5 of 10 videos per
  channel, mostly 0. They **are** on every recipe card checked. A
  description-only pipeline would fail our servings rule for most recipes.
- **Inline ingredient lists are a minority habit.** Only Sip and Feast does
  this consistently. Most large creators now put a link in the description and
  keep the recipe on their own (ad-funded) site.
- **The recipe card is the real source.** It is structured (WP Recipe Maker
  JSON-LD), has servings and gram weights more often than descriptions, and
  creators already maintain it. This supports Option A or B in 1.4.
- **Creators earn from site traffic.** A licence pitch that sends traffic back
  to their recipe page will land better than one that replaces it. Examples:
  a "Full method on [creator]'s site" link, plus the embed, which also pays
  them through YouTube ads.

---

## 3. Questions for a lawyer

1. **Derived data (III.E.4.h):** does parsing ingredient facts from
   API-fetched descriptions and keeping them count as "new or derived data"?
   Does a creator's licence change that, given that YouTube's terms bind us,
   not the creator? (Option A avoids the question.)
2. **Video IDs:** may we store video IDs beyond 30 days to drive embeds?
3. **Paid subscription with embeds (III.F.3.a):** does putting recipe pages
   with embedded videos behind a subscription count as charging users to watch
   embedded content?
4. **Creator licence template.** It should cover:
   - scope: ingredient data, servings, title, thumbnail or photo, video ID;
   - attribution and link-back;
   - use of name, likeness and brand in the app and in marketing (right of
     publicity; FTC Endorsement Guides if we pay them);
   - the creator's warranty that the recipe is theirs;
   - takedown and term;
   - fee or revenue share;
   - a clause that our nutrition numbers are ours and not endorsed by the
     creator.
5. **Website terms:** whether Raptive's *Terms of Content Use* and similar site
   terms are enforceable against reading a creator's recipe card without a
   licence.
6. **Food Wishes / Allrecipes**, if we ever want Chef John: who holds the
   recipe rights.

## Sources

YouTube and Google
- [Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
- [API Services Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service)
- [Developer Policies guide](https://developers.google.com/youtube/terms/developer-policies-guide)
- [Required Minimum Functionality](https://developers.google.com/youtube/terms/required-minimum-functionality)
- [YouTube Terms of Service](https://www.youtube.com/t/terms)

Copyright
- [US Copyright Office, Circular 33](https://www.copyright.gov/circs/circ33.pdf)
- [*Publications Int'l v. Meredith*, 88 F.3d 473 (7th Cir. 1996)](https://law.justia.com/cases/federal/appellate-courts/F3/88/473/486900/)
- [Bradley, "Intellectual Property Protection for Recipes" (2019)](https://www.bradley.com/-/media/files/insights/publications/2019/07/intellectual-property-protection-for-recipes.pdf)
- [Raptive, "What are Terms of Content Use?"](https://help.raptive.com/hc/en-us/articles/38873087079323-What-are-Terms-of-Content-Use)

Creators
- Channel pages and video descriptions at the YouTube links in the tables, read 2026-10-29
- Recipe cards: [natashaskitchen.com](https://natashaskitchen.com/slow-cooker-lasagna-recipe/), [downshiftology.com](https://downshiftology.com/recipes/greek-baked-cod/), [cleananddelicious.com](https://cleananddelicious.com/high-protein-lasagna-soup/), [theproteinchef.co](https://theproteinchef.co/slow-cooker-chicken-enchilada-soup-recipe/), [veganricha.com](https://www.veganricha.com/moroccan-harira/), [sipandfeast.com](https://www.sipandfeast.com/spinach-chicken-orzo/), [feelgoodfoodie.net](https://feelgoodfoodie.net/recipe/green-bean-casserole/), [budgetbytes.com](https://www.budgetbytes.com/potato-leek-soup/), [rainbowplantlife.com](https://rainbowplantlife.com/cabbage-soup/), [themediterraneandish.com](https://www.themediterraneandish.com/cabbage-soup/)
- Background:
  - [Clean & Delicious editorial policy](https://cleananddelicious.com/editorial-policies/)
  - [Feelgoodfoodie on SponsorRadar](https://sponsorradar.com/channels/feelgoodfoodie)
  - [Feelgoodfoodie on Finance Monthly](https://www.finance-monthly.com/?p=87592)
  - [Rainbow Plant Life meal plans](https://rainbowplantlife.com/?p=46853)
  - [Rainbow Plant Life about page](https://rainbowplantlife.com/about-nisha)
  - [BudgetBytes+](https://www.budgetbytes.com/join)
  - [Natasha's Kitchen "Work With Us"](https://natashaskitchen.com/?p=37746)
  - [Stealth Health x COUNTER](https://stealthhealthlife.substack.com/p/the-stealth-health-x-counter-story)
  - [Allrecipes acquires Food Wishes](https://www.prnewswire.com/news-releases/allrecipescom-acquires-food-wishes-in-major-push-to-dominate-the-online-food-video-space-127301528.html)
  - [My Nguyen at Penguin Random House](https://www.penguinrandomhouse.com/books/720029/healthy-my-way-by-my-nguyen/)
  - [Sip & Feast cookbook listing](https://fisherandfarmer.com/library/book/sip--feast-family-favorite-recipes-from-our-kitchen-to-yours-james-delmage/9798992066708)
