# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from Autodesk.Revit.DB import Revision

from System import Windows
from pyrevit.framework import wpf
import os
import json

from RevitUtils import get_model_info
from pyrevit.script import get_instance_data_file

xaml_file = os.path.join(os.path.dirname(__file__), "FiltersInViewsDialogUi.xaml")


class FiltersInViewsDialog(Windows.Window):
    def __init__(self, doc):
        wpf.LoadComponent(self, xaml_file)

        self.doc = doc

        self.settings = {

        }

        model_info = get_model_info(doc)
        self.setting_file_path = get_instance_data_file(
            "filters_in_views_settings-" + model_info["modelGuid"]
        )
        if os.path.exists(self.setting_file_path):
            with open(self.setting_file_path, "r") as file:
                setting_data = json.load(file)
                if setting_data:
                    for key, value in setting_data.items():
                        if key in self.settings:
                            self.settings[key] = value

        self.values_to_return = None

    def cancel_btn_click(self, sender, e):
        self.Close()

    def create_clouds_btn_click(self, sender, e):
        with open(self.setting_file_path, "w") as file:
            new_settings = {

            }
            json.dump(new_settings, file)

        self.Close()

    def show_dialog(self):
        self.ShowDialog()
        return self.values_to_return
