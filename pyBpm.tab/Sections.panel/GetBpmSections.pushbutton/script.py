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

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))

import SectionsScoring as scoring  # type: ignore
import SectionsFilterSelection as sfs  # type: ignore
from SectionsResultsWindow import SectionsResultsWindow, WINDOW_ENVVAR_KEY  # type: ignore
from pyrevit.forms import alert
from pyrevit import script

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
    # Duplicate-window guard (section 6): a second window would create a second
    # dc3d server - never allow it. If one is already open and visible, just
    # activate it. A stale/invalid handle is cleared and we proceed.
    existing = script.get_envvar(WINDOW_ENVVAR_KEY)
    if existing is not None:
        try:
            if existing.IsVisible:
                existing.Activate()
                return
        except Exception:
            pass
        # Not visible but a handle lingers (orphaned/half-closed). Close it so its
        # own Closed handler tears down its dc3d server before we build a new one
        # sharing the same fixed server GUID - otherwise the orphan's later
        # teardown could unregister the new window's server.
        try:
            existing.Close()
        except Exception:
            pass
        script.set_envvar(WINDOW_ENVVAR_KEY, None)

    comp_link, comp_doc, error = sfs.check_preconditions(doc)
    if error:
        alert(error)
        return

    # Candidate sections + sheets only - cheap, NO scoring (decision D1).
    items, sheets = scoring.get_candidate_sections_with_sheets(comp_doc)

    filters = _resolve_saved_filters(comp_doc)
    if not filters:
        # First run (or no valid saved selection): suggest the discipline group(s)
        # matching the opening families loaded in this model - the code the "Load
        # Opening Families" button stamped on their type Description. In-memory only
        # (not persisted), so it stays a smart default that follows the model until
        # the planner saves an explicit choice in Settings.
        filters = sfs.suggest_filters_from_openings(doc, comp_doc) or None

    window = SectionsResultsWindow(
        uidoc, comp_link, comp_doc, filters, items, sheets
    )
    script.set_envvar(WINDOW_ENVVAR_KEY, window)
    window.Show()


run()
