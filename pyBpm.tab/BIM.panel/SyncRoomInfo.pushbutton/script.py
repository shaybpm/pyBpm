# -*- coding: utf-8 -*-
__title__ = "Sync Room\nInformation"
__author__ = "BPM"
__doc__ = """Copies room number, name and level from linked models to the MEP and equipment elements located in those rooms.
Adds its shared parameters to the model on the first run.

Press F1 for a detailed explanation in Hebrew."""
__helpurl__ = "https://pybpm.azurewebsites.net/tutorials/pybpm-extension-syncroominfo"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
from SyncRoomInfo import main  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

app = __revit__.Application  # type: ignore
uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    main(app, doc)


run()
