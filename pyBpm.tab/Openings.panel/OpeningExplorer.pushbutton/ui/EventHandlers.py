# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (
    Transaction,
    TransactionGroup,
    BoundingBoxXYZ,
    XYZ,
    CategoryType,
)

from ExEventHandlers import get_simple_external_event
from ExternalEventDataFile import ExternalEventDataFile
from RevitUtils import get_ui_view, get_bpm_3d_view, turn_of_categories


def show_opening_3d_cb(uiapp):
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document

    ex_event_file = ExternalEventDataFile(doc)
    opening_dict = ex_event_file.get_key_value("opening_dict")
    opening_unique_id = opening_dict["unique_id"]
    opening_link_id = opening_dict["link_id"]


show_opening_3d_event = get_simple_external_event(show_opening_3d_cb)
