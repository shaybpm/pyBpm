# -*- coding: utf-8 -*-
""" Open a view of the model with the model quality auto checks results """
__title__ = "Model Quality\nAuto Checks"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from ServerUtils import is_model_quality_auto_checks_successful

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------

res = is_model_quality_auto_checks_successful(doc)
print(res)
