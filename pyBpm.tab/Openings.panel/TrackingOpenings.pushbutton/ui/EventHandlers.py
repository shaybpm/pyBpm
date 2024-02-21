# -*- coding: utf-8 -*-

import os, json
from Autodesk.Revit.DB import TransactionGroup
import Utils
from pyrevit.forms import alert
from pyrevit.script import get_instance_data_file
from RevitUtils import get_ui_view, get_bpm_3d_view, get_model_info
from ExEventHandlers import get_simple_external_event


class ExternalEventDataFile:
    def __init__(self, doc):
        model_info = get_model_info(doc)
        self.file_path = get_instance_data_file(
            "tracking_openings_data-" + model_info["modelGuid"]
        )

    def get_data(self):
        if not os.path.exists(self.file_path):
            return {}
        with open(self.file_path, "r") as file:
            data = json.load(file)
        return data

    def get_key_value(self, key):
        data = self.get_data()
        return data.get(key)

    def set_data(self, data):
        with open(self.file_path, "w") as file:
            json.dump(data, file)

    def set_key_value(self, key, value):
        data = self.get_data()
        data[key] = value
        self.set_data(data)


def show_opening_3d_cb(uiapp):
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document

    t_group = TransactionGroup(doc, "pyBpm | Show Opening 3D")
    t_group.Start()

    ex_event_file = ExternalEventDataFile(doc)
    opening = ex_event_file.get_key_value("current_selected_opening")
    current = ex_event_file.get_key_value("current_bool_arg")

    if not opening:
        return

    if current is None:
        return

    bbox = Utils.get_bbox(doc, opening, current)
    if not bbox:
        return

    ui_view = get_ui_view(uidoc)
    if not ui_view:
        return

    view_3d = get_bpm_3d_view(doc)
    if not view_3d:
        alert("תקלה בקבלת תצוגת 3D")
        return
    Utils.show_opening_3d(uidoc, ui_view, view_3d, bbox)
    t_group.Assimilate()


show_opening_3d_event = get_simple_external_event(show_opening_3d_cb)
