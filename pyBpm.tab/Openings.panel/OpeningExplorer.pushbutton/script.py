# -*- coding: utf-8 -*-
""" Opening Explorer """
__title__ = "Opening\nExplorer"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))
from OpeningExplorerDialog import OpeningExplorerDialog  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    dialog = OpeningExplorerDialog(uidoc)
    dialog.Show()


run()
