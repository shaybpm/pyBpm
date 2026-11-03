# -*- coding: utf-8 -*-
__title__ = "Model Quality\nAuto Checks"
__author__ = "BPM"
__doc__ = """Shows the automatic model quality check results of this model.
Shift+Click: open in a browser.

Press F1 for a detailed explanation in Hebrew."""
__helpurl__ = "https://pybpm.azurewebsites.net/tutorials/pybpm-extension-modelqualityautochecks"

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
