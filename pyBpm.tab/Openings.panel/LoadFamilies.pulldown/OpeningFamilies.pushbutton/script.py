# -*- coding: utf-8 -*-
""" Loads the BPM Opening families into the project.
families:
- M_Rectangular Face Opening Solid.rfa
- M_Round Face Opening Solid.rfa """
__title__ = "Opening\nFamilies"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import Transaction

from ..lib import LoadOpeningFamily

from pyrevit import forms

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def get_family_symbols(family):
    symbols = family.GetFamilySymbolIds()
    return [doc.GetElement(symbol) for symbol in symbols]


def run():
    descriptions = {
        "A - אדריכלות": "A",
        "S - קונסטרוקציה": "S",
        "P - אינסטלציה": "P",
        "SP - ספרינקלרים": "SP",
        "C - תקשורת": "C",
        "H - מיזוג אוויר": "H",
        "E - חשמל": "E",
        "G - גזים רפואיים": "G",
        "F - דלק": "F",
    }

    descriptions_selected = forms.SelectFromList.show(
        descriptions.keys(),
        title="Select Discipline",
        multiselect=False,
        button_name="Select",
    )
    if descriptions_selected is None:
        return
    descriptions_selected = descriptions[descriptions_selected]

    t = Transaction(doc, "BPM | Load Opening Families")
    t.Start()
    new_families = LoadOpeningFamily.run(
        doc, ["M_Rectangular Face Opening Solid", "M_Round Face Opening Solid"]
    )
    for family in new_families:
        family_sybols = get_family_symbols(family)
        for symbol in family_sybols:
            symbol.LookupParameter("Description").Set(descriptions_selected)
    t.Commit()


run()
