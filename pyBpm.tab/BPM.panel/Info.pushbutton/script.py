# -*- coding: utf-8 -*-
"""
- Show information about PyBpm.
- Show release notes.
- Link to the HOW-TO-DO.
"""
__title__ = "Info"
__author__ = "BPM"

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
