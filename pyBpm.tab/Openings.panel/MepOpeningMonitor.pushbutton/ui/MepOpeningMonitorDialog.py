# -*- coding: utf-8 -*-

import clr

clr.AddReferenceByPartialName("System")
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("System.Windows.Forms")
clr.AddReference("IronPython.Wpf")

from System import Windows
from System.Collections.Generic import List
import wpf
import os

from Autodesk.Revit.DB import ElementId

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

        grid = Windows.Controls.Grid()
        grid.ColumnDefinitions.Add(Windows.Controls.ColumnDefinition())
        grid.ColumnDefinitions.Add(Windows.Controls.ColumnDefinition())

        label = Windows.Controls.Label()
        label.SetValue(Windows.Controls.Grid.ColumnProperty, 0)
        label.Content = (
            element_result.mep_element.Category.Name
            + " - "
            + element_result.mep_element.Name
        )
        label.FontWeight = Windows.FontWeights.Bold

        grid.Children.Add(label)

        mep_controllers_stack_panel = Windows.Controls.StackPanel()
        mep_controllers_stack_panel.SetValue(Windows.Controls.Grid.ColumnProperty, 1)
        mep_controllers_stack_panel.Orientation = (
            Windows.Controls.Orientation.Horizontal
        )

        highlight_mep_button = Windows.Controls.Button()
        highlight_mep_button.Content = "Highlight MEP"
        highlight_mep_button.Margin = Windows.Thickness(12, 0, 0, 0)
        highlight_mep_button.Name = "HighlightMepButton_" + str(
            element_result.mep_element.Id
        )
        highlight_mep_button.Click += self.highlight_mep_button_click

        mep_controllers_stack_panel.Children.Add(highlight_mep_button)

        grid.Children.Add(mep_controllers_stack_panel)

        border.Child = grid
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

    def highlight_mep_button_click(self, sender, e):
        button = sender
        mep_id_int = int(button.Name.split("_")[-1])
        mep_id = ElementId(mep_id_int)
        ids = List[ElementId]([mep_id])
        self.uidoc.Selection.SetElementIds(ids)
        self.uidoc.ShowElements(ids)

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
