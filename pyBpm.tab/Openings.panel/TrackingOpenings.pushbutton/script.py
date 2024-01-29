# -*- coding: utf-8 -*-
""" Get the history changes of the project's openings """
__title__ = "Tracking\nOpenings"
__author__ = "BPM"
__highlight__ = "new"


# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import HttpRequest  # type: ignore
import ServerUtils  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    print("Hi")


run()
