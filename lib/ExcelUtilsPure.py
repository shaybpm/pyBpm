# -*- coding: utf-8 -*-
"""ExcelUtilsPure.py — pure-Python Excel utilities for pyRevit.

Replacement for the parts of ExcelUtils.py that don't need to drive a live
Excel application. Backed by xlsxwriter, which is bundled with pyRevit at
%APPDATA%\\pyRevit-Master\\site-packages\\xlsxwriter (no install needed).

Why this exists: ExcelUtils.py uses Microsoft.Office.Interop.Excel via COM.
That stops loading on Revit 25+ (the .NET 8 transition). xlsxwriter is pure
Python — works regardless of runtime, and does not require Excel to be
installed on the machine.

Notes for callers migrating from ExcelUtils.py:
 - xlsxwriter is write-only. Use xlrd (also bundled with pyRevit) for reads.
 - Cells are 0-indexed here, vs 1-indexed in COM (worksheet.Cells(r+1, c+1)).
 - Worksheet names: 31-char max; must not contain : \\ / ? * [ ].
 - Workbook is saved-and-closed in one call: workbook.close().
"""

import xlsxwriter  # noqa: F401 — re-exported so callers do one import

FIELD_DELIMITER = "|UNIQUESTRINGFORSEPARATOR|"
