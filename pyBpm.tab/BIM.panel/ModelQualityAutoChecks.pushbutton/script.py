# -*- coding: utf-8 -*-
"""
Open model quality auto checks results
Click with Shift to open in browser
"""
__title__ = "Model Quality\nAuto Checks"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from pyrevit import script
from RevitUtils import get_model_info
from PyRevitUtils import open_pybpm_page

from PyRevitUtils import ModelQualityAutoChecksToggleIcon

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

    model_info = get_model_info(doc)

    rel_target_html = "{}/model-quality-auto/{}".format(
        model_info["projectGuid"], model_info["modelGuid"]
    )
    rel_target_css = "styles/mq-model-auto.css"

    output = script.get_output() if not __shiftclick__ else None  # type: ignore

    open_pybpm_page(rel_target_html, rel_target_css, output)


run()
