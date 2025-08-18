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
from SRI_DialogResults import SRI_DialogResults, SRI_DialogResultsItem

xaml_file = os.path.join(os.path.dirname(__file__), "SRI_OneSourceModelPage.xaml")


class SRI_OneSourceModelPage(Windows.Controls.Page):
    def __init__(self, dialog_results):
        wpf.LoadComponent(self, xaml_file)
        self.dialog_results = dialog_results  # type: SRI_DialogResults
        self.initialize_combobox()

    def dialog_results_callback(self, sources, reservoir):
        if len(sources) == 0:
            self.sourceModelComboBox.SelectedItem = None
            return
        
        if len(sources) == 1:
            for combobox_item in self.sourceModelComboBox.Items:
                item = combobox_item.Tag
                if isinstance(item, SRI_DialogResultsItem) and item.is_valid() and item == sources[0]:
                    self.sourceModelComboBox.SelectedItem = combobox_item
                    break

    def initialize_combobox(self):
        # Initialize the ComboBox with source models
        self.sourceModelComboBox.Items.Clear()
        for item in self.dialog_results.all_items:
            if not item.is_valid():
                continue
            combobox_item = Windows.Controls.ComboBoxItem()
            combobox_item.Content = item.name
            combobox_item.Tag = item
            self.sourceModelComboBox.Items.Add(combobox_item)

    def sourceModelComboBox_SelectionChanged(self, sender, e):
        # Handle selection change in the ComboBox
        selected_item = self.sourceModelComboBox.SelectedItem
        if selected_item is not None:
            item = selected_item.Tag
            if isinstance(item, SRI_DialogResultsItem):
                self.dialog_results.clear_sources_and_add_one(item)
