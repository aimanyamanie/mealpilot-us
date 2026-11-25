-- 2026-11-24: allow course = 'component' for building blocks that are not meals
-- (stock, homemade butter, flavored oils, sauces, dressings, toppings).
-- Components keep meal_slots = '{}' so the planner never suggests them as a meal.
--   python apply_sql.py migrations/2026-11-24-component-course.sql
alter table recipes drop constraint if exists recipes_course_check;
alter table recipes add constraint recipes_course_check
    check (course in ('breakfast', 'main', 'side', 'snack', 'dessert', 'drink', 'component'));
alter table recipes add constraint recipes_component_not_plannable
    check (course is distinct from 'component' or meal_slots = '{}');
