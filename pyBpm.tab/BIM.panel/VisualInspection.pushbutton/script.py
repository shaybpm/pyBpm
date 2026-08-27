# -*- coding: utf-8 -*-
""" Visual Inspection.

Shows how the coordinator's architecture-structure visual inspection scored
this project - the model's score, then every inspection sheet and view with its
own score, worst first - read straight out of the compilation model. From any
section you can rebuild the same view in your own model, cut exactly where the
coordinator cut it, so you can go and fix what scored badly. """
__title__ = "Visual\nInspection"
__author__ = "Eyal Sinay"

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))

import RevitUtils  # extension-level lib
import VisualInspectionRead as read  # type: ignore
from VisualInspectionWindow import (  # type: ignore
    VisualInspectionWindow,
    WINDOW_ENVVAR_KEY,
)
from pyrevit.forms import alert
from pyrevit import script

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document


def run():
    # One window at a time. A second would keep its own External Event and its
    # own stale handles on the same document, and the planner would have two
    # lists disagreeing about what exists. An existing window is reused only if
    # it is alive AND belongs to THIS document: a window whose host document
    # was closed still reports IsVisible, and activating it hands back dead
    # handles that fail on every click (the T-0340 lesson from GetBpmSections).
    existing = script.get_envvar(WINDOW_ENVVAR_KEY)
    if existing is not None:
        try:
            reusable = (
                existing.IsVisible
                and not existing._closed
                and RevitUtils.is_valid(existing.doc)
                and existing.doc.Equals(doc)
            )
        except Exception:
            reusable = False
        if reusable:
            try:
                existing.Activate()
                return
            except Exception:
                pass
        try:
            existing.Close()
        except Exception:
            pass
        script.set_envvar(WINDOW_ENVVAR_KEY, None)

    comp_link, comp_doc, error = read.check_preconditions(doc)
    if error:
        alert(error)
        return

    window = VisualInspectionWindow(uidoc, comp_link)
    script.set_envvar(WINDOW_ENVVAR_KEY, window)
    window.Show()


run()
