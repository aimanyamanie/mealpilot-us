"""Read a filled-in review workbook into the sign-off files.

    python apply_review.py review/ingredient_review_2026-10-29.xlsx
    python build_seed.py && python validate_seed.py && python load_seed.py

Approvals go to signoffs.csv and portion_signoffs.csv, which are committed
and which build_seed.py honours. Each approval records what was approved:
the FDC id, the allergen and diet flags, and the portion's grams. If any of
those changes later, the approval stops applying and the row needs a new
review. "Fix" rows change nothing; they are written to review/fixes_<date>.md
to be corrected in ingredient_list.csv or usda_picks.csv.

Rows left blank keep whatever sign-off they already had.
"""
import csv
import sys
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
SIGNOFFS = HERE / "signoffs.csv"
PORTION_SIGNOFFS = HERE / "portion_signoffs.csv"
SIGNOFF_FIELDS = ["slug", "fdc_id", "nutrition", "flags_snapshot", "allergens", "diet",
                  "reviewer", "reviewed_on", "comment"]
PORTION_FIELDS = ["slug", "unit", "modifier", "grams", "status", "reviewer",
                  "reviewed_on", "comment"]
DECISIONS = {"Approve", "Fix"}


def text(v) -> str:
    return "" if v is None else str(v).strip()


def day(v) -> str:
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    return text(v) or date.today().isoformat()


def read_csv(path: Path, key) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {key(r): r for r in csv.DictReader(f)}


def write_csv(path: Path, fields: list[str], rows: dict) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])


def portion_key(r) -> tuple:
    return (r["slug"], r["unit"], r["modifier"])


def read_workbook(path: Path, seed: dict):
    """Returns (ingredient decisions, portion decisions, problems)."""
    wb = load_workbook(path, data_only=True)
    problems, ingredients, portions = [], [], []

    ws = wb["Ingredients"]
    head = [text(c.value) for c in ws[1]]
    col = {name: i for i, name in enumerate(head)}
    for n, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        slug = text(row[col["Slug"]])
        if not slug:
            continue
        nutrition, allergens, diet = (text(row[col[k]]) for k in
                                      ("Nutrition OK?", "Allergens OK?", "Diet OK?"))
        if not (nutrition or allergens or diet):
            continue
        reviewer, comment = text(row[col["Reviewer"]]), text(row[col["Correction / comment"]])
        where = f"Ingredients row {n} ({slug})"
        if slug not in seed:
            problems.append(f"{where}: not in the current seed")
            continue
        bad = {nutrition, allergens, diet} - DECISIONS - {""}
        if bad:
            problems.append(f"{where}: {sorted(bad)} is not Approve or Fix")
            continue
        if not reviewer:
            problems.append(f"{where}: a decision needs a Reviewer name")
            continue
        if "Fix" in (nutrition, allergens, diet) and not comment:
            problems.append(f"{where}: Fix needs a Correction / comment")
            continue
        ingredients.append({
            "slug": slug, "fdc_id": text(row[col["FDC id"]]), "nutrition": nutrition,
            # What the reviewer saw, in allergen_summary()'s format.
            "flags_snapshot": f"{text(row[col['Allergens (as entered)']])} | "
                              f"{text(row[col['Animal source']])}",
            "allergens": allergens,
            "diet": diet, "reviewer": reviewer, "reviewed_on": day(row[col["Date"]]),
            "comment": comment,
        })

    ws = wb["Portions"]
    head = [text(c.value) for c in ws[1]]
    col = {name: i for i, name in enumerate(head)}
    for n, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        status = text(row[col["Portion OK?"]])
        if not status:
            continue
        slug = text(row[col["Slug"]])
        reviewer, comment = text(row[col["Reviewer"]]), text(row[col["Correction / comment"]])
        where = f"Portions row {n} ({slug})"
        if status not in DECISIONS:
            problems.append(f"{where}: {status!r} is not Approve or Fix")
        elif not reviewer:
            problems.append(f"{where}: a decision needs a Reviewer name")
        elif status == "Fix" and not comment:
            problems.append(f"{where}: Fix needs a Correction / comment")
        else:
            modifier = text(row[col["Modifier"]])
            portions.append({
                "slug": slug, "unit": text(row[col["Unit"]]),
                "modifier": "" if modifier == "(none)" else modifier,
                "grams": f"{float(row[col['Grams per 1 unit']]):g}", "status": status,
                "reviewer": reviewer, "reviewed_on": date.today().isoformat(),
                "comment": comment,
            })
    return ingredients, portions, problems


def merge(existing: dict, new: dict) -> dict:
    """A blank decision in the new review keeps the earlier one."""
    if not existing:
        return new
    merged = dict(new)
    for field in ("nutrition", "allergens", "diet"):
        if not new[field]:
            merged[field] = existing[field]
    if not new["nutrition"]:
        merged["fdc_id"] = existing["fdc_id"]
    if not (new["allergens"] or new["diet"]):
        merged["flags_snapshot"] = existing["flags_snapshot"]
    return merged


def fixes_report(ingredients, portions) -> str:
    lines = [f"# Review fixes, {date.today().isoformat()}", "",
             "Each item needs a correction in `ingredient_list.csv` or `usda_picks.csv` "
             "(or a measured portion), then build, validate, load and review again.", ""]
    for r in ingredients:
        parts = [k for k in ("nutrition", "allergens", "diet") if r[k] == "Fix"]
        if parts:
            lines.append(f"- **{r['slug']}** ({', '.join(parts)}, {r['reviewer']}): {r['comment']}")
    for r in portions:
        if r["status"] == "Fix":
            mod = f" {r['modifier']}" if r["modifier"] else ""
            lines.append(f"- **{r['slug']}** portion 1 {r['unit']}{mod} = {r['grams']} g "
                         f"({r['reviewer']}): {r['comment']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        sys.exit(__doc__)
    with (HERE / "ingredients_seed.csv").open(encoding="utf-8", newline="") as f:
        seed = {r["slug"]: r for r in csv.DictReader(f)}
    ingredients, portions, problems = read_workbook(Path(argv[0]), seed)
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        print(f"{len(problems)} problems: nothing written. Fix the workbook and run again.")
        return 1

    signoffs = read_csv(SIGNOFFS, lambda r: r["slug"])
    for r in ingredients:
        signoffs[r["slug"]] = merge(signoffs.get(r["slug"]), r)
    write_csv(SIGNOFFS, SIGNOFF_FIELDS, signoffs)

    portion_signoffs = read_csv(PORTION_SIGNOFFS, portion_key)
    for r in portions:
        portion_signoffs[portion_key(r)] = r
    write_csv(PORTION_SIGNOFFS, PORTION_FIELDS, portion_signoffs)

    report = fixes_report(ingredients, portions)
    fixes = report.count("\n- ")
    if fixes:
        out = HERE / "review" / f"fixes_{date.today().isoformat()}.md"
        out.write_text(report, encoding="utf-8")
        print(f"{fixes} fixes listed in {out.relative_to(HERE)}")
    approved = sum(1 for r in ingredients if "Approve" in (r["nutrition"], r["allergens"], r["diet"]))
    print(f"read {len(ingredients)} ingredient and {len(portions)} portion decisions "
          f"({approved} ingredients with an approval)")
    print("next: python build_seed.py && python validate_seed.py && python load_seed.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
