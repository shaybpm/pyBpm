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

xaml_file = os.path.join(os.path.dirname(__file__), "SRI_MultipleSourceModelsPage.xaml")


class SRI_MultipleSourceModelsPage(Windows.Controls.Page):
    def __init__(self, dialog_results):
        wpf.LoadComponent(self, xaml_file)
        self.dialog_results = dialog_results  # type: SRI_DialogResults
        self.initialize_combobox_and_listbox()

    def dialog_results_callback(self, sources, reservoir):
        self.initialize_combobox_and_listbox()

    def initialize_combobox_and_listbox(self):
        sources = self.dialog_results.sources
        reservoir = self.dialog_results.reservoir

        self.sourceModelsListBox.Items.Clear()
        for item in sources:
            if not item.is_valid():
                continue
            listbox_item = Windows.Controls.ListBoxItem()
            listbox_item.Content = item.name
            listbox_item.Tag = item
            self.sourceModelsListBox.Items.Add(listbox_item)

        self.reservoirModelComboBox.Items.Clear()
        for item in reservoir:
            if not item.is_valid():
                continue
            combobox_item = Windows.Controls.ComboBoxItem()
            combobox_item.Content = item.name
            combobox_item.Tag = item
            self.reservoirModelComboBox.Items.Add(combobox_item)
        if self.reservoirModelComboBox.Items.Count > 0:
            self.reservoirModelComboBox.SelectedIndex = 0

    def selectReservoirModelButton_click(self, sender, e):
        selected_item = self.reservoirModelComboBox.SelectedItem
        if selected_item is not None:
            item = selected_item.Tag
            if isinstance(item, SRI_DialogResultsItem):
                self.dialog_results.add_to_sources(item)

    def removeSourceModelButton_click(self, sender, e):
        selected_item = self.sourceModelsListBox.SelectedItem
        if selected_item is not None:
            item = selected_item.Tag
            if isinstance(item, SRI_DialogResultsItem):
                self.dialog_results.remove_from_sources(item)

    def clearSourceModelsButton_click(self, sender, e):
        self.dialog_results.clear_sources()
        
    def select_item_in_listbox(self, dialog_res_item): # type: (SRI_DialogResultsItem) -> None
        # Select the item in the ListBox
        for item in self.sourceModelsListBox.Items:
            if isinstance(item, Windows.Controls.ListBoxItem) and item.Tag == dialog_res_item:
                self.sourceModelsListBox.SelectedItem = item
                return

    def raisingPriorityButton_click(self, sender, e):
        selected_item = self.sourceModelsListBox.SelectedItem
        if selected_item is not None:
            item = selected_item.Tag
            if isinstance(item, SRI_DialogResultsItem):
                self.dialog_results.raise_source_priority(item)
                self.select_item_in_listbox(item)  # Re-select to update UI

    def loweringPriorityButton_click(self, sender, e):
        selected_item = self.sourceModelsListBox.SelectedItem
        if selected_item is not None:
            item = selected_item.Tag
            if isinstance(item, SRI_DialogResultsItem):
                self.dialog_results.lower_source_priority(item)
                self.select_item_in_listbox(item)  # Re-select to update UI
