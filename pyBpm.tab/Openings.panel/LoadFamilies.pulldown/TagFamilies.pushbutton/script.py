# -*- coding: utf-8 -*-
""" Loads the BPM Tag Opening families into the project.
families:
- BPM Opening Tag (R20).rfa
- BPM Opening Tag (R22).rfa """
__title__ = "Tag Families"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.UI import TaskDialog

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
import LoadOpeningFamily  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document


def alert(msg):
    TaskDialog.Show("BPM - Load Opening Family", msg)


# --------------------------------
# -------------SCRIPT-------------
# --------------------------------

LoadOpeningFamily.run(doc, ["BPM Opening Tag (R22)", "BPM Opening Tag (R20)"])
