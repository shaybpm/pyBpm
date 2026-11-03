# -*- coding: utf-8 -*-
__title__ = "Coordination\nPrep Missing"
__author__ = "BPM"
__doc__ = """Lists the missing items BPM found for this model in coordination prep, with zoom and 3D to each one.

Press F1 for a detailed explanation in Hebrew."""
__helpurl__ = "https://pybpm.azurewebsites.net/tutorials/pybpm-extension-coordprepmissing"

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

from CoordPrepMissingUI import show  # noqa: E402

show(__revit__.ActiveUIDocument)  # type: ignore
