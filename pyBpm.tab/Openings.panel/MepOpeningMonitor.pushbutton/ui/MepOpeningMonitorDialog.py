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

    def get_button_style(self):
        button_style = Windows.Style()
        button_style.Setters.Add(
            Windows.Setter(
                Windows.Controls.Button.PaddingProperty, Windows.Thickness(8)
            )
        )
        button_style.Setters.Add(
            Windows.Setter(
                Windows.Controls.Button.BackgroundProperty,
                Windows.Media.SolidColorBrush(
                    Windows.Media.Color.FromRgb(255, 223, 51)
                ),
            )
        )
        button_style.Setters.Add(
            Windows.Setter(
                Windows.Controls.Button.ForegroundProperty,
                Windows.Media.SolidColorBrush(Windows.Media.Color.FromRgb(0, 51, 102)),
            )
        )
        button_style.Setters.Add(
            Windows.Setter(
                Windows.Controls.Button.BorderBrushProperty,
                Windows.Media.Brushes.Transparent,
            )
        )
        button_style.Setters.Add(
            Windows.Setter(
                Windows.Controls.Button.CursorProperty,
                Windows.Input.Cursors.Hand,
            )
        )
        border_style = Windows.Style(Windows.Controls.Border)
        border_style.Setters.Add(
            Windows.Setter(
                Windows.Controls.Border.CornerRadiusProperty,
                Windows.CornerRadius(4),
            )
        )

        return button_style

    def add_result(self, element_result):
        mep_and_intersect_stack_panel = Windows.Controls.StackPanel()

        mep_and_intersect_border = Windows.Controls.Border()
        mep_and_intersect_border.BorderThickness = Windows.Thickness(1)
        mep_and_intersect_border.BorderBrush = Windows.Media.Brushes.Gray
        mep_and_intersect_border.Margin = Windows.Thickness(0, 12, 0, 0)
        mep_and_intersect_border.CornerRadius = Windows.CornerRadius(4)

        mep_grid = Windows.Controls.Grid()
        mep_grid.ColumnDefinitions.Add(Windows.Controls.ColumnDefinition())
        mep_grid.ColumnDefinitions.Add(Windows.Controls.ColumnDefinition())
        mep_grid.Background = Windows.Media.SolidColorBrush(
            Windows.Media.Color.FromRgb(0, 51, 102)
        )

        mep_label = Windows.Controls.Label()
        mep_label.SetValue(Windows.Controls.Grid.ColumnProperty, 0)
        mep_label.Content = (
            element_result.mep_element.Category.Name
            + " - "
            + element_result.mep_element.Name
        )
        mep_label.FontWeight = Windows.FontWeights.Bold
        mep_label.Foreground = Windows.Media.Brushes.White
        mep_label.VerticalAlignment = Windows.VerticalAlignment.Center

        mep_controllers_stack_panel = Windows.Controls.StackPanel()
        mep_controllers_stack_panel.SetValue(Windows.Controls.Grid.ColumnProperty, 1)
        mep_controllers_stack_panel.Orientation = (
            Windows.Controls.Orientation.Horizontal
        )

        highlight_mep_button = Windows.Controls.Button()
        highlight_mep_button.Content = "Highlight MEP"
        highlight_mep_button.Margin = Windows.Thickness(12)
        highlight_mep_button.Name = "HighlightMepButton_" + str(
            element_result.mep_element.Id
        )
        highlight_mep_button.Style = self.get_button_style()
        highlight_mep_button.Click += self.highlight_mep_button_click

        mep_controllers_stack_panel.Children.Add(highlight_mep_button)

        mep_grid.Children.Add(mep_label)
        mep_grid.Children.Add(mep_controllers_stack_panel)

        mep_and_intersect_stack_panel.Children.Add(mep_grid)

        mep_and_intersect_border.Child = mep_and_intersect_stack_panel

        self.StackPanelMain.Children.Add(mep_and_intersect_border)

        for index, intersect_res in enumerate(
            element_result.intersect_with_concrete_result
        ):
            intersect_grid = Windows.Controls.Grid()
            intersect_grid.ColumnDefinitions.Add(Windows.Controls.ColumnDefinition())
            intersect_grid.ColumnDefinitions.Add(Windows.Controls.ColumnDefinition())
            intersect_grid.Background = (
                Windows.Media.SolidColorBrush(
                    Windows.Media.Color.FromRgb(102, 153, 255)
                )
                if index % 2 == 0
                else Windows.Media.SolidColorBrush(
                    Windows.Media.Color.FromRgb(153, 204, 255)
                )
            )

            intersect_label = Windows.Controls.Label()
            intersect_label.SetValue(Windows.Controls.Grid.ColumnProperty, 0)
            intersect_label.Content = intersect_res.intersect_element.Category.Name
            intersect_label.Margin = Windows.Thickness(24, 0, 0, 0)
            intersect_label.VerticalAlignment = Windows.VerticalAlignment.Center

            intersect_controllers_stack_panel = Windows.Controls.StackPanel()
            intersect_controllers_stack_panel.SetValue(
                Windows.Controls.Grid.ColumnProperty, 1
            )
            intersect_controllers_stack_panel.Orientation = (
                Windows.Controls.Orientation.Horizontal
            )

            intersect_button = Windows.Controls.Button()
            intersect_button.Content = "Section Box"
            intersect_button.Margin = Windows.Thickness(12)
            intersect_button.Name = "SectionBoxButton_{}_{}".format(
                element_result.mep_element.Id,
                index,
            )
            intersect_button.Style = self.get_button_style()
            intersect_button.Click += self.section_box_button_click

            intersect_controllers_stack_panel.Children.Add(intersect_button)

            intersect_grid.Children.Add(intersect_label)
            intersect_grid.Children.Add(intersect_controllers_stack_panel)

            # intersect_border.Child = intersect_grid
            mep_and_intersect_stack_panel.Children.Add(intersect_grid)

    def highlight_mep_button_click(self, sender, e):
        button = sender
        mep_id_int = int(button.Name.split("_")[-1])
        mep_id = ElementId(mep_id_int)
        ids = List[ElementId]([mep_id])
        self.uidoc.Selection.SetElementIds(ids)
        self.uidoc.ShowElements(ids)

    def section_box_button_click(self, sender, e):
        button = sender
        name_split = button.Name.split("_")
        mep_id_int = int(name_split[-2])
        mep_id = ElementId(mep_id_int)
        index = int(name_split[-1])

        intersect_res = None
        for res in self.res_current:
            if res.mep_element.Id == mep_id:
                intersect_res = res.intersect_with_concrete_result[index]
                break

        if intersect_res is None:
            return

        print(intersect_res.intersect_bounding_box)

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
