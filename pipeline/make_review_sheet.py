"""Write a review workbook for signing off the ingredient seed.

    python make_review_sheet.py      # -> review/ingredient_review_<date>.xlsx

One row per ingredient (USDA record, nutrition, allergens) and one per
portion, each with yellow columns for the reviewer. The seed CSVs stay
the source of truth: an approved or corrected row goes back into
ingredient_list.csv / usda_picks.csv, then build, validate and load.
"""
import csv
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "review"
FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
INPUT_FILL = PatternFill("solid", fgColor="FFFF00")
LOOK_FILL = PatternFill("solid", fgColor="F8CBAD")
THIN = Side(style="thin", color="BFBFBF")
ALLERGENS = [("has_milk", "milk"), ("has_egg", "egg"), ("has_fish", "fish"),
             ("has_shellfish", "shellfish"), ("has_tree_nut", "tree nut"),
             ("has_peanut", "peanut"), ("has_wheat", "wheat"), ("has_soy", "soy"),
             ("has_sesame", "sesame"), ("has_gluten", "gluten"), ("has_alcohol", "alcohol")]


def allergen_summary(seed_row: dict) -> str:
    """What the reviewer saw: 'milk, gluten | dairy'. A sign-off only holds
    while this is unchanged, so editing the flags reopens the review."""
    allergens = ", ".join(label for col, label in ALLERGENS if str(seed_row[col]) == "True")
    return f"{allergens or 'none'} | {seed_row['animal_source'] or 'plant'}"


def read(name):
    with (HERE / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    return float(v) if v not in ("", None) else None


def header(ws, row, titles, widths, input_from=None):
    for col, (title, width) in enumerate(zip(titles, widths), start=1):
        c = ws.cell(row=row, column=col, value=title)
        is_input = input_from is not None and col >= input_from
        c.font = Font(name=FONT, bold=True, color="000000" if is_input else "FFFFFF")
        c.fill = INPUT_FILL if is_input else HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[row].height = 32


def style_body(ws, first, last, ncols, input_from):
    for r in range(first, last + 1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=r, column=c)
            cell.font = Font(name=FONT, size=10)
            cell.border = Border(bottom=THIN)
            cell.alignment = Alignment(vertical="top", wrap_text=c in WRAP_COLS.get(ws.title, ()))
            if c >= input_from:
                cell.fill = INPUT_FILL


WRAP_COLS = {"Ingredients": (5, 6, 19, 27), "Portions": (7, 10)}


def ingredients_sheet(wb, seed, picks):
    ws = wb.create_sheet("Ingredients")
    titles = ["Slug", "Name", "Category", "FDC id", "USDA description", "Pick note",
              "Data quality", "kcal /100g", "Protein g", "Carb g", "Fat g", "Fiber g",
              "Sugar g", "Sodium mg", "kcal from macros", "Macro check",
              "Allergens (as entered)", "Animal source", "Allergen note",
              "Portions", "USDA page",
              "Nutrition OK?", "Allergens OK?", "Diet OK?", "Reviewer", "Date", "Correction / comment"]
    widths = [24, 28, 12, 10, 44, 34, 11, 9, 9, 9, 9, 9, 9, 10, 10, 10,
              22, 12, 34, 9, 9, 12, 12, 10, 12, 12, 40]
    input_from = 22
    header(ws, 1, titles, widths, input_from)
    for i, s in enumerate(seed, start=2):
        fdc = s["source_ref"].replace("FDC ", "")
        allergens = ", ".join(label for col, label in ALLERGENS if s[col] == "True")
        values = [s["slug"], s["name"], s["category"], int(fdc), s["source_description"],
                  picks[s["slug"]]["pick_note"], s["data_quality"],
                  *(num(s[k]) for k in ("kcal_100g", "protein_100g", "carb_100g", "fat_100g",
                                        "fiber_100g", "sugar_100g", "sodium_mg_100g"))]
        for col, v in enumerate(values, start=1):
            ws.cell(row=i, column=col, value=v)
        # Atwater with fiber at 2 kcal/g, the same rule as validate_seed.py
        ws.cell(row=i, column=15, value=f'=IF(H{i}="","",ROUND(4*N(I{i})+4*(N(J{i})-N(L{i}))+2*N(L{i})+9*N(K{i}),0))')
        if s["macro_check_exempt"]:
            ws.cell(row=i, column=16, value=f"exempt: {s['macro_check_exempt']}")
        else:
            ws.cell(row=i, column=16, value=f'=IF(OR(H{i}="",O{i}=""),"",IF(ABS(O{i}-H{i})>MAX(20,0.2*H{i}),"look",""))')
        ws.cell(row=i, column=17, value=allergens or "none")
        ws.cell(row=i, column=18, value=s["animal_source"] or "plant")
        ws.cell(row=i, column=19, value=s["allergens_note"])
        ws.cell(row=i, column=20, value=f"=COUNTIF(Portions!$A:$A,A{i})")
        link = ws.cell(row=i, column=21,
                       value=f'=HYPERLINK("https://fdc.nal.usda.gov/food-details/{fdc}/nutrients","open")')
        link.font = Font(name=FONT, size=10, color="0563C1", underline="single")
    last = len(seed) + 1
    style_body(ws, 2, last, len(titles), input_from)
    for col in range(8, 16):
        for r in range(2, last + 1):
            ws.cell(row=r, column=col).number_format = "0.0"
    for r in range(2, last + 1):
        ws.cell(row=r, column=21).font = Font(name=FONT, size=10, color="0563C1", underline="single")
    ok = DataValidation(type="list", formula1='"Approve,Fix"', allow_blank=True)
    ws.add_data_validation(ok)
    ok.add(f"V2:X{last}")
    ws.conditional_formatting.add(f"P2:P{last}", FormulaRule(formula=[f'P2="look"'], fill=LOOK_FILL))
    ws.conditional_formatting.add(f"H2:N{last}", FormulaRule(formula=['H2=""'], fill=LOOK_FILL))
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(titles))}{last}"
    return last


def portions_sheet(wb, portions, names):
    ws = wb.create_sheet("Portions")
    titles = ["Slug", "Ingredient", "Unit", "Modifier", "Grams per 1 unit", "Default?",
              "Source", "Portion OK?", "Reviewer", "Correction / comment"]
    widths = [24, 28, 9, 13, 11, 9, 44, 12, 12, 40]
    input_from = 8
    header(ws, 1, titles, widths, input_from)
    for i, p in enumerate(portions, start=2):
        values = [p["slug"], names[p["slug"]], p["unit"], p["modifier"] or "(none)",
                  float(p["grams"]), "yes" if p["is_default"] == "True" else "",
                  p["source_ref"] if p["source"] == "USDA" else f"{p['source']}: {p['source_ref']}"]
        for col, v in enumerate(values, start=1):
            ws.cell(row=i, column=col, value=v)
    last = len(portions) + 1
    style_body(ws, 2, last, len(titles), input_from)
    for r in range(2, last + 1):
        ws.cell(row=r, column=5).number_format = "0.0"
    ok = DataValidation(type="list", formula1='"Approve,Fix"', allow_blank=True)
    ws.add_data_validation(ok)
    ok.add(f"H2:H{last}")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:J{last}"
    return last


def gaps_sheet(wb, seed, portions):
    ws = wb.create_sheet("Gaps")
    header(ws, 1, ["Slug", "Name", "Gap", "What would fix it"], [24, 28, 34, 60])
    with_portions = {p["slug"] for p in portions}
    by_weight = {"meat", "poultry"}
    rows = []
    for s in seed:
        for key, label in (("sugar_100g", "sugar"), ("fiber_100g", "fiber")):
            if s[key] == "":
                rows.append((s["slug"], s["name"], f"USDA publishes no {label}",
                             f"A {label} value from another reliable source, or a decision that it rounds to 0"))
        if s["slug"] not in with_portions and s["category"] not in by_weight:
            rows.append((s["slug"], s["name"], "No cup or piece weight",
                         "Weigh a cup or one piece, or take it from a product label"))
        if s["data_quality"] == "researched":
            rows.append((s["slug"], s["name"], "Uses a stand-in USDA record",
                         "Confirm the stand-in is close enough, or source a label"))
    for i, row in enumerate(rows, start=2):
        for col, v in enumerate(row, start=1):
            c = ws.cell(row=i, column=col, value=v)
            c.font = Font(name=FONT, size=10)
            c.alignment = Alignment(vertical="top", wrap_text=col == 4)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:D{len(rows) + 1}"


def guide_sheet(ws, ing_last, por_last):
    ws.title = "How to review"
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 40
    bold = Font(name=FONT, bold=True, size=14)
    ws["A1"] = "MealPilot US: ingredient sign-off"
    ws["A1"].font = bold
    ws["A2"] = f"Generated {date.today().isoformat()} from pipeline/ingredients_seed.csv (225 rows) and ingredient_portions_seed.csv."
    lines = [
        "What to do",
        "1. Edit only the yellow columns. Everything else is generated and will be overwritten.",
        "2. Ingredients tab: for each row, open the USDA page if needed and set Nutrition OK?, Allergens OK? and Diet OK? to Approve or Fix.",
        "3. Nutrition: check the USDA description is the food the name means, and the macros fit it. 'look' in Macro check means calories and macros disagree by more than 20%.",
        "4. Allergens: FDA's 9 major allergens, plus gluten and alcohol. Brand-dependent items say so in Allergen note; approve the rule for a typical product.",
        "5. Diet: Animal source drives vegetarian and vegan. 'plant' means none.",
        "6. Anything you set to Fix needs a short Correction / comment saying what is wrong and, if known, the right value or record.",
        "7. Portions tab: check grams look right for one unit (one medium onion, one cup chopped). Defaults are what a recipe line without a size uses.",
        "8. Gaps tab: missing values USDA does not publish. No action needed to approve the rest.",
        "Coloured cells: yellow = yours to fill in. Pink = a value missing, or a macro check to look at.",
    ]
    for r, text in enumerate(lines, start=4):
        c = ws.cell(row=r, column=1, value=text)
        c.font = Font(name=FONT, bold=(r == 4) or text.startswith("Coloured"), size=10)
    ws["A15"] = "Example of a filled-in row (format only; not a real review)"
    ws["A15"].font = Font(name=FONT, bold=True, size=10)
    example_head = ["Slug", "Nutrition OK?", "Allergens OK?", "Diet OK?", "Correction / comment"]
    example = ["worcestershire", "Approve", "Fix", "Approve",
               "Lea & Perrins US label lists no wheat: drop gluten for this brand"]
    for col, (h, v) in enumerate(zip(example_head, example), start=1):
        ws.cell(row=16, column=col, value=h).font = Font(name=FONT, bold=True, size=10)
        c = ws.cell(row=17, column=col, value=v)
        c.font = Font(name=FONT, size=10, italic=True)
        c.fill = INPUT_FILL
    ws["A19"] = "Progress"
    ws["A19"].font = Font(name=FONT, bold=True, size=10)
    progress = [
        ("Ingredients", f"=COUNTA(Ingredients!A2:A{ing_last})"),
        ("Nutrition approved", f'=COUNTIF(Ingredients!V2:V{ing_last},"Approve")'),
        ("Allergens approved", f'=COUNTIF(Ingredients!W2:W{ing_last},"Approve")'),
        ("Diet approved", f'=COUNTIF(Ingredients!X2:X{ing_last},"Approve")'),
        ("Rows marked Fix", f'=COUNTIF(Ingredients!V2:X{ing_last},"Fix")'),
        ("Portions", f"=COUNTA(Portions!A2:A{por_last})"),
        ("Portions approved", f'=COUNTIF(Portions!H2:H{por_last},"Approve")'),
    ]
    for r, (label, formula) in enumerate(progress, start=20):
        ws.cell(row=r, column=1, value=label).font = Font(name=FONT, size=10)
        ws.cell(row=r, column=2, value=formula).font = Font(name=FONT, size=10)
    ws["A28"] = ("Source: USDA FoodData Central bulk downloads, Foundation Foods 2026-10 and SR Legacy 2018-04 "
                 "(public domain). Records were chosen by Claude from their descriptions; this review is the human sign-off.")
    ws["A28"].font = Font(name=FONT, size=9, italic=True)


def main(out_dir: Path = OUT_DIR) -> Path:
    seed = read("ingredients_seed.csv")
    portions = read("ingredient_portions_seed.csv")
    picks = {r["slug"]: r for r in read("usda_picks.csv")}
    names = {s["slug"]: s["name"] for s in seed}
    wb = Workbook()
    guide = wb.active
    ing_last = ingredients_sheet(wb, seed, picks)
    por_last = portions_sheet(wb, portions, names)
    gaps_sheet(wb, seed, portions)
    guide_sheet(guide, ing_last, por_last)
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"ingredient_review_{date.today().isoformat()}.xlsx"
    wb.save(out)
    print(out)
    return out


if __name__ == "__main__":
    main()
