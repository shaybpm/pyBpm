# -*- coding: utf-8 -*-
""" Get information about opening changes in this project """
__title__ = "Tracking\nOpenings"
__author__ = "BPM"
__highlight__ = "new"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from ServerUtils import ServerPermissions  # type: ignore
from pyrevit import forms

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))
from TrackingOpeningsDialog import TrackingOpeningsDialog  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document


# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    server_permissions = ServerPermissions(doc)
    openings_tracking_permission = server_permissions.get_openings_tracking_permission()
    if not openings_tracking_permission:
        forms.alert(
            "אין לפרויקט זה גישה לאפשרות זו",
            title="אין גישה לפרויקט",
        )
        return
    dialog = TrackingOpeningsDialog(uidoc)

    if __shiftclick__:  # type: ignore
        dialog.ShowDialog()
    else:
        dialog.Show()


run()
