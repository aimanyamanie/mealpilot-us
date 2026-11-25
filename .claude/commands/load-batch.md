---
description: Test, load every recipe into Neon, and commit (after the chat Claude has prepared the batch)
argument-hint: <commit message>
---
Load the prepared recipe batch into Neon, then commit. Work in `pipeline/`. Stop at the first failure and report it; never edit files to make a step pass.

1. `python -m pytest -q tests`: all tests must pass.
2. `python load_ingredients.py`: loads units, ingredients and USDA records (needs network to api.nal.usda.gov and the Neon host in `.env`; if the sandbox blocks it, rerun outside the sandbox).
3. `python load_recipe.py --check` with every file in `recipes/*.json`: must exit 0. Report any `ERROR` or `!` lines.
4. `python load_recipe.py` with every file in `recipes/*.json` (same list, without `--check`).
5. `git status`, then stage only `CLAUDE.md`, `docs/`, `.claude/commands/` and `pipeline/` (never `.env`, `.env.bak*` or `pipeline/data/`). Commit with the message "$ARGUMENTS" and push.

Reply briefly:
- the test count
- the number of recipes loaded, and any recipe that loaded as `draft`
- any warning lines
- the commit hash
