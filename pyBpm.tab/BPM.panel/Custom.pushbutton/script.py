# -*- coding: utf-8 -*-
__title__ = "Custom"
__author__ = "BPM"
__doc__ = """Opens a list of extra BPM tools.

Press F1 for a detailed explanation in Hebrew."""
__helpurl__ = "https://pybpm.azurewebsites.net/tutorials/pybpm-extension-custom"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from pyrevit.forms import SelectFromList

import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
import Custom # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------



def run():
    scripts = Custom.common_scripts() + Custom.custom_scripts(doc)
    selected_script = SelectFromList.show(
        scripts,
        title="Select a script to run",
        multiselect=False,
    )
    if not selected_script:
        return
    
    Custom.run_by_name(selected_script, uidoc)


run()
