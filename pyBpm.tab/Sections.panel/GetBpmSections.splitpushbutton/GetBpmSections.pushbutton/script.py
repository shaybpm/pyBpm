# -*- coding: utf-8 -*-
""" Get Bpm Sections.

Opens the modeless results window that scores how well your current model
already matches the coordinator's compilation-model sections, so you can see
which sections need attention, and create / go to / delete the section in your
model. The window opens on its Home page and computes nothing until you pick a
sheet. Replaces the old multi-select section picker. """
__title__ = "Get Bpm\nSections"
__author__ = "Eyal Sinay"

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "ui"))

import SectionsScoring as scoring  # type: ignore
import SectionsFilterSelection as sfs  # type: ignore
from SectionsResultsWindow import SectionsResultsWindow  # type: ignore
from pyrevit.forms import alert

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document


def _resolve_saved_filters(comp_doc):
    """Return the saved discipline filters for this (model, comp) pair when a
    complete, still-valid selection exists, else None. No window is popped - a
    missing selection just leaves the sheet buttons locked (D9) until the planner
    opens Settings from inside the window. Reuses the lib's own resolution."""
    saved_ids = sfs.load_saved_selection(doc, comp_doc)
    if not saved_ids:
        return None
    groups = sfs.collect_discipline_filters(comp_doc)
    if not groups:
        return None
    preselected, all_present = sfs._resolve_saved(comp_doc, groups, saved_ids)
    if not all_present or not preselected:
        return None
    return preselected


def run():
    comp_link, comp_doc, error = sfs.check_preconditions(doc)
    if error:
        alert(error)
        return

    # Candidate sections + sheets only - cheap, NO scoring (decision D1).
    items, sheets = scoring.get_candidate_sections_with_sheets(comp_doc)

    filters = _resolve_saved_filters(comp_doc)

    window = SectionsResultsWindow(
        uidoc, comp_link, comp_doc, filters, items, sheets
    )
    window.Show()


run()
