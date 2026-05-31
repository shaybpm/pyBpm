# -*- coding: utf-8 -*-
""" Hides openings (in linked models) that fall below the active plan view's primary
view range - openings only visible through the view-depth / underlay zone.

Builds a vertical band from the bottom of the view range down to the lower of the
view-depth / underlay-bottom planes, finds every opening in the linked models whose
bounding box sits fully inside that band, and rebuilds a per-view filter that hides
exactly those openings (the filter is reset on every run).

Requires a plan view (has a View Range) with no View Template. """
__title__ = "Hide By\nView Range"
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

    bbox, error = hide.build_band_bounding_box(doc, view)
    if error:
        hide.alert(error)
        return

    openings_data, found_count = hide.collect_openings_below_range(doc, bbox)

    specific_filter = hide.update_and_apply_view_filter(
        doc, view, openings_data, reset=True
    )
    if not specific_filter:
        hide.alert("יצירת הפילטר נכשלה.")
        return

    if found_count:
        hide.alert(
            "הוסתרו {} פתחים הנמצאים מתחת ל-View Range של המבט.".format(found_count)
        )
    else:
        hide.alert(
            "לא נמצאו פתחים מתחת ל-View Range של המבט.\n"
            "הפילטר עודכן בהתאם (לא הוסתרו פתחים)."
        )


run()
