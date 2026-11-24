-- 2026-11-16: record where each ingredient amount came from.
-- Rule (Aiman): amounts come from the transcript first; when the transcript is
-- unclear, use the creator's written recipe as the reference; otherwise we estimate.
-- quantity_basis still says whose amount it is for THIS dish (stated / estimated /
-- to_taste); amount_source says where the number came from.
--   python apply_sql.py migrations/2026-11-16-amount-source.sql

alter table recipe_ingredients
    add column amount_source     text check (amount_source in ('transcript', 'creator_recipe', 'our_estimate')),
    add column amount_source_url text,    -- the creator's written recipe page
    add column amount_note       text;    -- how the number was taken or scaled

update recipe_ingredients set amount_source = case quantity_basis
    when 'stated' then 'transcript'
    when 'estimated' then 'our_estimate' end;

alter table recipe_ingredients
    add constraint recipe_ingredients_amount_source_fits_basis check (
        (quantity_basis = 'to_taste'  and amount_source is null) or
        (quantity_basis = 'stated'    and amount_source in ('transcript', 'creator_recipe')) or
        (quantity_basis = 'estimated' and amount_source in ('creator_recipe', 'our_estimate'))),
    add constraint recipe_ingredients_creator_recipe_has_url check (
        (amount_source = 'creator_recipe') = (amount_source_url is not null)),
    add constraint recipe_ingredients_creator_recipe_has_note check (
        amount_source is distinct from 'creator_recipe' or amount_note is not null);
