# -*- coding: utf-8 -*-
__title__ = "Model Quality\nReport"
__author__ = "BPM"
__doc__ = """Opens the Model Quality Report of this model.
Shift+Click: open in a browser.

Press F1 for a detailed explanation in Hebrew."""
__helpurl__ = "https://pybpm.azurewebsites.net/tutorials/pybpm-extension-modelqualityreport"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from pyrevit import script
from RevitUtils import get_model_info
from PyRevitUtils import open_pybpm_page

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    model_info = get_model_info(doc)

    rel_target_html = "{}/model-quality/{}".format(
        model_info["projectGuid"], model_info["modelGuid"]
    )
    rel_target_css = "styles/mq-model.css"

    output = script.get_output() if not __shiftclick__ else None  # type: ignore

    open_pybpm_page(rel_target_html, rel_target_css, output)


run()
