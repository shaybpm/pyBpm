# -*- coding: utf-8 -*-

import clr

clr.AddReferenceByPartialName("System")
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("System.Windows.Forms")
clr.AddReference("IronPython.Wpf")

from System import Windows
import wpf
import os


xaml_file = os.path.join(os.path.dirname(__file__), "MepOpeningMonitorDialogUi.xaml")


class MepOpeningMonitorDialog(Windows.Window):
    def __init__(self, uidoc, results):
        wpf.LoadComponent(self, xaml_file)

        self.uidoc = uidoc
        self.doc = self.uidoc.Document
        self.res_source = results
        self.res_current = results

        self.render_results()

    def filter_results(self):
        filtered = []
        for res in self.res_source:
            # TODO
            filtered.append(res)

        self.res_current = filtered

    def sort_results(self):
        def sort_func(element_result):
            level_id = element_result.mep_element.LevelId
            level = self.doc.GetElement(level_id)
            return level.ProjectElevation

        self.res_current = sorted(self.res_current, key=sort_func)

    def clear_results(self):
        self.StackPanelMain.Children.Clear()

    def add_level(self, level_id):
        level = self.doc.GetElement(level_id)
        level_name = level.Name

        label = Windows.Controls.Label()
        label.Content = level_name
        label.FontWeight = Windows.FontWeights.Bold
        label.FontSize = 16
        label.HorizontalAlignment = Windows.HorizontalAlignment.Center
        label.Margin = Windows.Thickness(0, 12, 0, 0)

        self.StackPanelMain.Children.Add(label)

    def add_result(self, element_result):
        border = Windows.Controls.Border()
        border.BorderThickness = Windows.Thickness(1)
        border.BorderBrush = Windows.Media.Brushes.Gray
        border.Margin = Windows.Thickness(0, 12, 0, 0)

        label = Windows.Controls.Label()
        label.Content = (
            element_result.mep_element.Category.Name
            + " - "
            + element_result.mep_element.Name
        )
        label.FontWeight = Windows.FontWeights.Bold

        border.Child = label
        self.StackPanelMain.Children.Add(border)

        for intersect_res in element_result.intersect_with_concrete_result:
            border = Windows.Controls.Border()
            border.BorderThickness = Windows.Thickness(1, 0, 1, 1)
            border.BorderBrush = Windows.Media.Brushes.Gray

            label = Windows.Controls.Label()
            label.Content = intersect_res.intersect_element.Category.Name
            label.Margin = Windows.Thickness(24, 0, 0, 0)

            border.Child = label
            self.StackPanelMain.Children.Add(border)

    def render_results(self):
        self.filter_results()
        self.sort_results()

        self.clear_results()

        for index, res in enumerate(self.res_current):
            if (
                index == 0
                or res.mep_element.LevelId
                != self.res_current[index - 1].mep_element.LevelId
            ):
                self.add_level(res.mep_element.LevelId)

            self.add_result(res)
