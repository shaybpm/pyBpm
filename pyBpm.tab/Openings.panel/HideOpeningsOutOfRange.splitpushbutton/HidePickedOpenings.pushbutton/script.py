# -*- coding: utf-8 -*-
""" Hides openings (in linked models) that you pick manually.

Asks you to pick opening elements in the linked models, then asks whether to reset
the view's hidden-openings filter or add the picked openings to it, and applies the
per-view filter (hides the matches).

Requires a plan view with no View Template. """
__title__ = "Hide Picked\nOpenings"
__author__ = "BPM"

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
import HideOpenings as hide  # type: ignore

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document


def run():
    view, error = hide.validate_active_view(doc)
    if error:
        hide.alert(error)
        return

    picked = hide.pick_openings(uidoc)
    if picked is None:
        return  # user cancelled the selection
    openings_data, found_count = picked
    if not openings_data:
        hide.alert("לא נבחרו פתחים תקינים (פתח חייב Discipline ו-Mark).")
        return

    reset = hide.ask_reset_or_add()
    if reset is None:
        return  # user cancelled the question

    specific_filter = hide.update_and_apply_view_filter(
        doc, view, openings_data, reset=reset
    )
    if not specific_filter:
        hide.alert("יצירת הפילטר נכשלה.")
        return

    if reset:
        hide.alert("הפילטר אותחל. הוסתרו {} פתחים נבחרים.".format(found_count))
    else:
        hide.alert(
            "{} פתחים נבחרים נוספו לפתחים המוסתרים במבט.".format(found_count)
        )


run()
