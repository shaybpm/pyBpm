# -*- coding: utf-8 -*-
""" Settings for Get Bpm Sections.

Opens the discipline-filter selection window so the planner can choose and save
which compilation-model filters define the systems to match. The selection is
stored locally per user, scoped to the current model and the compilation model. """
__title__ = "Settings"
__author__ = "BPM"

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))

import SectionsFilterSelection as sfs  # type: ignore
from pyrevit.forms import alert

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document


def run():
    result = sfs.ensure_filter_selection(doc, force_window=True)
    status = result["status"]
    if status == "blocked":
        alert(result["message"])
        return
    if status == "cancelled":
        return
    alert(u"נשמרה בחירה של {} פילטרים.".format(len(result["filters"])))


run()
