# -*- coding: utf-8 -*-
""" Get information about opening changes in this project.

To get all options available for the user, run the script with the shift key pressed. """
__title__ = "Tracking\nOpenings"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from RevitUtils import get_link_types_status
from ServerUtils import ServerPermissions
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
    if not doc.IsModelInCloud:
        forms.alert(
            "אפשרות זו זמינה רק עבור פרויקטים בענן",
            title="פרויקט לא בענן",
        )
        return
    server_permissions = ServerPermissions(doc)
    openings_tracking_permission = False
    try:
        openings_tracking_permission = (
            server_permissions.get_openings_tracking_permission()
        )
    except Exception as e:
        msg = "שגיאה:\n{}".format(e)
        if str(e) == "Unable to connect to the remote server":
            msg = "יש לוודא חיבור תקין לאינטרנט."
        forms.alert(
            msg,
            title="שגיאה בבדיקת הרשאות",
        )
        return
    if not openings_tracking_permission:
        forms.alert(
            "אין לפרויקט זה גישה לאפשרות זו",
            title="אין גישה לפרויקט",
        )
        return
    dialog = TrackingOpeningsDialog(uidoc)

    link_types_status = get_link_types_status(doc)
    unloaded_links = link_types_status.get(
        "LocallyUnloaded", []
    ) + link_types_status.get("Unloaded", [])
    if len(unloaded_links) > 0:
        message = (
            "שים לב, יש לינק שאינו טעון, לא ניתן יהיה לקבל את הפתחים של לינק זה.\nשם הלינק:\n"
            if len(unloaded_links) == 1
            else "שים לב, ישנם {} לינקים לא טעונים, לא ניתן יהיה לקבל את הפתחים של לינקים אלה.\nשמות הלינקים:\n".format(
                len(unloaded_links)
            )
        )
        message += ", ".join(unloaded_links)
        forms.alert(message)

    dialog.Show()


run()
