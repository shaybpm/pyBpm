# -*- coding: utf-8 -*-
"""
Coordination prep - the missing items BPM found for this model,
with zoom and 3D to each one.
"""
__title__ = "Coordination\nPrep Missing"
__author__ = "BPM"

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

from CoordPrepMissingUI import show  # noqa: E402

show(__revit__.ActiveUIDocument)  # type: ignore
