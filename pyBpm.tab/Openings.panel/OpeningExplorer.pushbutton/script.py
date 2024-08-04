# -*- coding: utf-8 -*-
""" Opening Explorer is a simple tool to help you navigate through the openings in the project. """
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
