# -*- coding: utf-8 -*-
"""This script copies room data (number, name, and level) from selected source models to elements in the predefined categories. If the required shared parameters do not exist, they will be created automatically on the first run."""
__title__ = "Sync Room\nInformation"
__author__ = "BPM"

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
