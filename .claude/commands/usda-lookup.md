---
description: Look up USDA candidates for a recipe batch (read-only), for the chat Claude to pick from
argument-hint: <batch name, e.g. batch3>
---
Run the USDA lookup for batch `$ARGUMENTS`. This only reads from the USDA API and writes to the gitignored `pipeline/data/` folder.

1. From `pipeline/`, run `python data/lookup_usda.py $ARGUMENTS`. It needs network access to api.nal.usda.gov. If the sandbox blocks it (NameResolutionError or proxy error), rerun the same command outside the sandbox.
2. It prints progress and ends with `wrote ... | queries: N | errors: E`. If E > 0, run it once more: results are cached, so only the failures are retried.
3. Reply with that last line only. Don't edit any file, don't pick USDA records, and don't touch the database: the chat Claude picks the records.
