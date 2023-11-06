# -*- coding: utf-8 -*-
""" Loads the BPM Opening families into the project.
families:
- M_Rectangular Face Opening Solid.rfa
- M_Round Face Opening Solid.rfa """
__title__ = "Opening Families"
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

LoadOpeningFamily.run(
    doc, ["M_Rectangular Face Opening Solid", "M_Round Face Opening Solid"]
)
