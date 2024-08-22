# -*- coding: utf-8 -*-
""" Settings for MepOpeningMonitor """
__title__ = "Settings"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from pyrevit import forms

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))
from MepOpeningMonitorSettingsDialog import MepOpeningMonitorSettingsDialog  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    if not doc.IsModelInCloud:
        forms.alert("This model is not in the cloud.")
        return
    dialog = MepOpeningMonitorSettingsDialog(doc)
    dialog.ShowDialog()


run()
