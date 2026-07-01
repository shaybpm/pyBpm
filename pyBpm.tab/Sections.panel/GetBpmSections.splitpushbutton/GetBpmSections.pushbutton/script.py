# -*- coding: utf-8 -*-
""" Get Bpm Sections.

Opens the modeless results window that scores how well your current model
already matches the coordinator's compilation-model sections, so you can see
which sections need attention. Section create / go-to / delete actions are added
in a later phase. Replaces the old multi-select section picker. """
__title__ = "Get Bpm\nSections"
__author__ = "Eyal Sinay"

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "ui"))

import SectionsFilterSelection as sfs  # type: ignore
from SectionsResultsDialog import SectionsResultsDialog  # type: ignore
from pyrevit.forms import alert

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document


def run():
    comp_link, comp_doc, error = sfs.check_preconditions(doc)
    if error:
        alert(error)
        return

    selection = sfs.ensure_filter_selection(doc, force_window=False)
    if selection["status"] == "blocked":
        alert(selection["message"])
        return
    if selection["status"] == "cancelled":
        return

    dialog = SectionsResultsDialog(uidoc, comp_link, comp_doc, selection["filters"])
    dialog.Show()


run()
