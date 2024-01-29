# -*- coding: utf-8 -*-
""" Loads the BPM Tag Opening families into the project.
families:
- BPM Opening Tag (R20).rfa
- BPM Opening Tag (R22).rfa """
__title__ = "Tag\nFamilies"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import Transaction

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
import LoadOpeningFamily  # type: ignore

from RevitUtils import getRevitVersion  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

families = (
    [
        "BPM Opening Tag (R20)",
    ]
    if getRevitVersion(doc) < 2022
    else [
        "BPM Opening Tag (R22)",
    ]
)

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------
t = Transaction(doc, "BPM | Load Opening Tag Families")
t.Start()
LoadOpeningFamily.run(doc, families)
t.Commit()
