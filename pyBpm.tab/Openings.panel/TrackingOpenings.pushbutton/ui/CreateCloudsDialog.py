# -*- coding: utf-8 -*-

import clr

clr.AddReferenceByPartialName("System")
clr.AddReference("System.Windows.Forms")
clr.AddReference("IronPython.Wpf")

from Autodesk.Revit.DB import Revision

from System import Windows
import wpf
import os
import json

from RevitUtils import get_model_info
from pyrevit.script import get_instance_data_file

xaml_file = os.path.join(os.path.dirname(__file__), "CreateCloudsDialogUi.xaml")


class CreateCloudsDialog(Windows.Window):
    def __init__(self, doc):
        wpf.LoadComponent(self, xaml_file)

        self.doc = doc

        self.settings = {
            "create_revision_radiobutton_is_checked": True,
            "select_revision_radiobutton_is_checked": False,
            "current_revision_selected": "",
            "cloud_size_small_radiobutton_is_checked": True,
            "cloud_size_medium_radiobutton_is_checked": False,
            "cloud_size_large_radiobutton_is_checked": False,
        }

        model_info = get_model_info(doc)
        self.setting_file_path = get_instance_data_file(
            "create_clouds_dialog_settings-" + model_info["modelGuid"]
        )
        if os.path.exists(self.setting_file_path):
            with open(self.setting_file_path, "r") as file:
                setting_data = json.load(file)
                if setting_data:
                    for key, value in setting_data.items():
                        if key in self.settings:
                            self.settings[key] = value

        all_revisions_ids = Revision.GetAllRevisionIds(doc)
        self.all_revisions = [doc.GetElement(x) for x in all_revisions_ids]
        rev_strings = [
            "{} - {}".format(rev.RevisionDate, rev.Description)
            for rev in self.all_revisions
        ]
        for rev in rev_strings:
            self.existing_revisions_combobox.Items.Add(rev)

        if self.settings["current_revision_selected"] in rev_strings:
            self.existing_revisions_combobox.SelectedIndex = rev_strings.index(
                self.settings["current_revision_selected"]
            )

        self.create_revision_radiobutton.IsChecked = self.settings[
            "create_revision_radiobutton_is_checked"
        ]
        self.select_revision_radiobutton.IsChecked = self.settings[
            "select_revision_radiobutton_is_checked"
        ]
        self.cloud_size_small_radiobutton.IsChecked = self.settings[
            "cloud_size_small_radiobutton_is_checked"
        ]
        self.cloud_size_medium_radiobutton.IsChecked = self.settings[
            "cloud_size_medium_radiobutton_is_checked"
        ]
        self.cloud_size_large_radiobutton.IsChecked = self.settings[
            "cloud_size_large_radiobutton_is_checked"
        ]

        self.create_revision_radiobutton.Checked += (
            self.create_or_select_revision_checked
        )
        self.select_revision_radiobutton.Checked += (
            self.create_or_select_revision_checked
        )
        self.handle_existing_revisions_combobox_is_enabled()

        self.values_to_return = None

    def handle_existing_revisions_combobox_is_enabled(self):
        if self.create_revision_radiobutton.IsChecked:
            self.existing_revisions_combobox.IsEnabled = False
        elif self.select_revision_radiobutton.IsChecked:
            self.existing_revisions_combobox.IsEnabled = True

    def create_or_select_revision_checked(self, sender, e):
        self.handle_existing_revisions_combobox_is_enabled()
        if self.create_revision_radiobutton.IsChecked:
            self.existing_revisions_combobox.SelectedIndex = -1

    def get_cloud_size(self):
        if self.cloud_size_small_radiobutton.IsChecked:
            return "small"
        elif self.cloud_size_medium_radiobutton.IsChecked:
            return "medium"
        elif self.cloud_size_large_radiobutton.IsChecked:
            return "large"

    def cancel_btn_click(self, sender, e):
        self.Close()

    def create_clouds_btn_click(self, sender, e):
        if self.create_revision_radiobutton.IsChecked:
            self.values_to_return = {
                "create_revision": True,
                "revision": None,
                "cloud_size": self.get_cloud_size(),
            }
        else:
            selected_revision = self.all_revisions[
                self.existing_revisions_combobox.SelectedIndex
            ]
            self.values_to_return = {
                "create_revision": False,
                "revision": selected_revision,
                "cloud_size": self.get_cloud_size(),
            }

        with open(self.setting_file_path, "w") as file:
            new_settings = {
                "create_revision_radiobutton_is_checked": self.create_revision_radiobutton.IsChecked,
                "select_revision_radiobutton_is_checked": self.select_revision_radiobutton.IsChecked,
                "current_revision_selected": self.existing_revisions_combobox.SelectedValue,
                "cloud_size_small_radiobutton_is_checked": self.cloud_size_small_radiobutton.IsChecked,
                "cloud_size_medium_radiobutton_is_checked": self.cloud_size_medium_radiobutton.IsChecked,
                "cloud_size_large_radiobutton_is_checked": self.cloud_size_large_radiobutton.IsChecked,
            }
            json.dump(new_settings, file)

        self.Close()

    def show_dialog(self):
        self.ShowDialog()
        return self.values_to_return
