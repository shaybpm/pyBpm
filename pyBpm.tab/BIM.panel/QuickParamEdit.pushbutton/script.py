# -*- coding: utf-8 -*-
""" Quick Parameter Edit - bulk-edit parameter values by category. """
__title__ = "Quick\nParam Edit"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))
from QuickParamEditDialog import QuickParamEditDialog  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    dialog = QuickParamEditDialog(uidoc)
    dialog.ShowDialog()  # Modal - allows a direct Transaction without an External Event


run()
