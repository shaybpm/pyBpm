# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
import wpf
import os

from ServerUtils import ProjectStructuralModels

from UiUtils import get_button_style1
from RevitUtils import get_all_link_instances

xaml_file = os.path.join(
    os.path.dirname(__file__), "MepOpeningMonitorSettingsDialogUi.xaml"
)


class MepOpeningMonitorSettingsDialog(Windows.Window):
    def __init__(self, doc):
        wpf.LoadComponent(self, xaml_file)

        self.doc = doc
        self.project_structural_models = ProjectStructuralModels(doc)

        self.models = (
            [
                {
                    "name": "{} (Current Model)".format(doc.Title),
                    "guid": doc.GetCloudModelPath().GetModelGUID().ToString(),
                }
            ]
            if doc.IsModelInCloud
            else []
        )
        all_links = get_all_link_instances(doc)
        for link in all_links:
            doc_link = link.GetLinkDocument()
            if not doc_link:
                continue
            if not doc_link.IsModelInCloud:
                continue
            model_guid = doc_link.GetCloudModelPath().GetModelGUID().ToString()
            if model_guid in [x["guid"] for x in self.models]:
                continue
            self.models.append(
                {
                    "name": doc_link.Title,
                    "guid": model_guid,
                }
            )

        self.init_ui()

    def init_ui(self):
        structural_models_stack_panel = self.structural_models_stack_panel
        for model in self.models:
            checkbox = Windows.Controls.CheckBox()
            checkbox.Content = model["name"]
            checkbox.Tag = model["guid"]
            checkbox.IsChecked = (
                model["guid"] in self.project_structural_models.structural_models
            )
            checkbox.Margin = Windows.Thickness(0, 0, 0, 4)
            structural_models_stack_panel.Children.Add(checkbox)

        btn_style_1 = get_button_style1()
        self.save_button.Style = btn_style_1
        self.cancel_button.Style = btn_style_1

    def SaveButton_Click(self, sender, e):
        structural_models = []
        for child in self.structural_models_stack_panel.Children:
            if not isinstance(child, Windows.Controls.CheckBox):
                continue
            if child.IsChecked:
                structural_models.append(child.Tag)
        self.project_structural_models.set_structural_models(structural_models)
        self.Close()

    def CancelButton_Click(self, sender, e):
        self.Close()
