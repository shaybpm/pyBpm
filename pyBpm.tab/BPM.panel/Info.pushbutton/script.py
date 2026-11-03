# -*- coding: utf-8 -*-
__title__ = "Info"
__author__ = "BPM"
__doc__ = """Shows what pyBpm is, the installed version, whether a newer one exists, and a link to the guide.

Press F1 for a detailed explanation in Hebrew."""
__helpurl__ = "https://pybpm.azurewebsites.net/tutorials/pybpm-extension-info"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))
from PyBpmInfo import PyBpmInfo  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------


# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    window = PyBpmInfo()
    window.ShowDialog()


run()
