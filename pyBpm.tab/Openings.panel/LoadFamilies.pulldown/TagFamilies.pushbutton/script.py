# -*- coding: utf-8 -*-
""" Loads the BPM Tag Opening families into the project. """
__title__ = "Tag\nFamilies"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import TransactionGroup

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
import LoadOpeningFamily  # type: ignore

from RevitUtils import getRevitVersion

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
    if getRevitVersion(doc) < 2023
    else [
        "BPM Opening Tag (R23)",
    ]
)

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------
t_group = TransactionGroup(doc, "BPM | Load Opening Families")
t_group.Start()
LoadOpeningFamily.run(doc, families)
t_group.Assimilate()
