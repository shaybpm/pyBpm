# -*- coding: utf-8 -*-
""" Open a view of the model with the model quality auto checks results """
__title__ = "Model Quality\nAuto Checks"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from pyrevit import forms

from PyRevitUtils import ModelQualityAutoChecksToggleIcon
from ServerUtils import get_filtered_model_quality_auto_checks

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    model_quality_auto_checks_toggle_icon = ModelQualityAutoChecksToggleIcon(doc)
    model_quality_auto_checks_toggle_icon.set_icon()

    checks = get_filtered_model_quality_auto_checks(doc)
    if not checks:
        forms.alert("No model quality auto checks data found.")
        return

    for check in checks:
        print(check)


run()
