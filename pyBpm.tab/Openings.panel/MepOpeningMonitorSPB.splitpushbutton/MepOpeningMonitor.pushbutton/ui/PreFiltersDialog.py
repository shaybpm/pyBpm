# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from pyrevit.framework import wpf
import os

from Autodesk.Revit.DB import ElementId

from RevitUtils import get_levels_sorted
from UiUtils import get_button_style1

xaml_file = os.path.join(os.path.dirname(__file__), "PreFiltersDialogUi.xaml")


class PreFiltersDialog(Windows.Window):
    def __init__(self, doc):
        wpf.LoadComponent(self, xaml_file)
        self.doc = doc

        self.temp_results = {
            "levels": [],
        }
        self.results = None

        self.initial_ui()
        self.initial_options()

    def initial_ui(self):
        self.OK_btn = get_button_style1()
        self.Cancel_btn = get_button_style1()

    def initial_options(self):
        self.levels = get_levels_sorted(self.doc)
        for level in self.levels:
            checkBox = Windows.Controls.CheckBox()
            checkBox.FontSize = 14
            checkBox.Content = level.Name
            checkBox.Tag = level.Id.IntegerValue
            checkBox.Checked += self.on_filter_checkbox_checked
            checkBox.Unchecked += self.on_filter_checkbox_unchecked
            self.StackPanelMain.Children.Add(checkBox)

    def on_filter_checkbox_checked(self, sender, e):
        level_id = ElementId(sender.Tag)
        self.temp_results["levels"].append(level_id)

    def on_filter_checkbox_unchecked(self, sender, e):
        level_id = ElementId(sender.Tag)
        self.temp_results["levels"].remove(level_id)

    def OK_btn_Click(self, sender, e):
        self.results = self.temp_results
        self.Close()

    def Cancel_btn_Click(self, sender, e):
        self.Close()

    def show_dialog(self):
        self.ShowDialog()
        return self.results
