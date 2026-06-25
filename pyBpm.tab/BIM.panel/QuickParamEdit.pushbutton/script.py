# -*- coding: utf-8 -*-
""" Quick Parameter Edit - bulk-edit parameter values by category. """
__title__ = "Quick\nParam Edit"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import sys, os, traceback

sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    # Import inside run() so an import-time failure (e.g. a missing assembly on a
    # given Revit/.NET version) is caught and shown as a real traceback instead of
    # an empty pyRevit output window.
    from QuickParamEditDialog import QuickParamEditDialog  # type: ignore

    dialog = QuickParamEditDialog(uidoc)
    dialog.ShowDialog()  # Modal - allows a direct Transaction without an External Event


try:
    run()
except Exception:
    print("Quick Param Edit failed to open:\n" + traceback.format_exc())
    raise
