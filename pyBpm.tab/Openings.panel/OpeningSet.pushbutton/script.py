# -*- coding: utf-8 -*-
""" This script iterates over all the openings and set their parameters according to the BPM standards.

To get the full results of the script, hold Shift and click the button. """
__title__ = "Opening\nSet"
__author__ = "Ely Komm & Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import Transaction
from Autodesk.Revit.UI import TaskDialog

from pyrevit import script
import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
import OpeningSet  # type: ignore
import PrintResults  # type: ignore
from RevitUtilsOpenings import get_all_openings

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

output = script.get_output()
output.close_others()


def alert(msg):
    TaskDialog.Show("BPM - Opening Update", msg)


# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    all_openings = get_all_openings(doc)
    if len(all_openings) == 0:
        alert("No openings found.")
        return

    t = Transaction(doc, "BPM | Opening Set")
    t.Start()

    failOpt = t.GetFailureHandlingOptions()
    preprocessor = OpeningSet.Preprocessor()
    failOpt.SetFailuresPreprocessor(preprocessor)
    t.SetFailureHandlingOptions(failOpt)

    results = OpeningSet.execute_all_functions_for_all_openings(doc, all_openings, True)

    if __shiftclick__:  # type: ignore
        PrintResults.print_full_results(output, results)
    else:
        PrintResults.print_results(output, results)

    t.Commit()


run()
