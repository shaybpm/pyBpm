# -*- coding: utf-8 -*-
__title__ = "Tag\nFamilies"
__author__ = "Eyal Sinay"
__doc__ = """Loads the BPM opening tag family into the model.

Press F1 for a detailed explanation in Hebrew."""
__helpurl__ = "https://pybpm.azurewebsites.net/tutorials/pybpm-extension-tagfamilies"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import TransactionGroup

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
import LoadOpeningFamily  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

families = [
    "BPM Opening Tag (R23)",
]

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------
t_group = TransactionGroup(doc, "BPM | Load Opening Families")
t_group.Start()
LoadOpeningFamily.run(doc, families)
t_group.Assimilate()
