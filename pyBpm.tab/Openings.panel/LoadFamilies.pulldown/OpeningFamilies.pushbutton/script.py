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

from Autodesk.Revit.DB import Transaction, TransactionGroup

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
import LoadOpeningFamily  # type: ignore
import OverwriteFamily  # type: ignore

from pyrevit import forms
from RevitUtils import get_family_symbols

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

shiftclick = __shiftclick__  # type: ignore

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------

family_names = ["M_Rectangular Face Opening Solid", "M_Round Face Opening Solid"]


def run():
    if shiftclick:
        # to_continue = forms.alert(
        #     "\n".join(
        #         [
        #             "⚠️ Important Warning!",
        #             "This operation will overwrite existing families in the model.",
        #             "Please ensure that the model is saved or synchronized before proceeding.",
        #             "After the script completes, review the model carefully.",
        #             "If any issues are found, you can undo the changes or reload the last saved version.",
        #             "",
        #             "Are you sure you want to continue?",
        #         ]
        #     ),
        #     title="Overwrite Families",
        #     yes=True,
        #     no=True,
        # )
        # if not to_continue:
        #     return
        OverwriteFamily.run(doc, family_names)
        return

    descriptions_selected, _ = LoadOpeningFamily.get_discipline_from_user()
    if not descriptions_selected:
        return

    new_families = LoadOpeningFamily.run(doc, family_names)
    t = Transaction(doc, "BPM | Load Opening Families")
    t.Start()
    for family in new_families:
        family_symbols = get_family_symbols(family)
        for symbol in family_symbols:
            symbol.LookupParameter("Description").Set(descriptions_selected)
    t.Commit()


run()
