# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from System.Collections.Generic import List
import wpf
import os

from pyrevit import forms

from Autodesk.Revit.DB import ElementId, XYZ

from RevitUtils import get_min_max_points_from_bbox, get_ui_view
from UiUtils import get_button_style1
from ReusableExternalEvents import show_bbox_3d_event
from ExternalEventDataFile import ExternalEventDataFile

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
        return
        filtered = []
        for res in self.res_source:
            # TODO
            filtered.append(res)

        self.res_current = filtered

    def sort_results(self):
        # def sort_func(element_result):
        #     level_id = element_result.found_in_level_id
        #     level = self.doc.GetElement(level_id)
        #     return level.ProjectElevation

        # self.res_current = sorted(self.res_current, key=sort_func)
        pass

    def clear_results(self):
        self.StackPanelMain.Children.Clear()

    # def add_level(self, level_id):
    #     level = self.doc.GetElement(level_id)
    #     level_name = level.Name

    #     label = Windows.Controls.Label()
    #     label.Content = level_name
    #     label.FontWeight = Windows.FontWeights.Bold
    #     label.FontSize = 16
    #     label.HorizontalAlignment = Windows.HorizontalAlignment.Center
    #     label.Margin = Windows.Thickness(0, 12, 0, 0)

    #     self.StackPanelMain.Children.Add(label)

    def add_result(self, element_result):
        mep_and_intersect_stack_panel = Windows.Controls.StackPanel()

        mep_and_intersect_border = Windows.Controls.Border()
        mep_and_intersect_border.BorderThickness = Windows.Thickness(1)
        mep_and_intersect_border.BorderBrush = Windows.Media.Brushes.Gray
        mep_and_intersect_border.Margin = Windows.Thickness(0, 12, 0, 0)
        mep_and_intersect_border.CornerRadius = Windows.CornerRadius(4)

        mep_grid = Windows.Controls.Grid()
        mep_grid.ColumnDefinitions.Add(Windows.Controls.ColumnDefinition())
        mep_grid_ColumnDefinition_1 = Windows.Controls.ColumnDefinition()
        mep_grid_ColumnDefinition_1.Width = Windows.GridLength(160)
        mep_grid.ColumnDefinitions.Add(mep_grid_ColumnDefinition_1)
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
        highlight_mep_button.Margin = Windows.Thickness(4)
        highlight_mep_button.Name = "HighlightMepButton_" + str(
            element_result.mep_element.Id
        )
        highlight_mep_button.Style = get_button_style1()
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
            intersect_grid_columnDefinition_2 = Windows.Controls.ColumnDefinition()
            intersect_grid_columnDefinition_2.Width = Windows.GridLength(160)
            intersect_grid.ColumnDefinitions.Add(intersect_grid_columnDefinition_2)

            intersect_label = Windows.Controls.Label()
            intersect_label.SetValue(Windows.Controls.Grid.ColumnProperty, 0)
            intersect_label.Content = intersect_res.intersect_element.Category.Name
            # intersect_label.Margin = Windows.Thickness(24, 0, 0, 0)
            intersect_label.VerticalAlignment = Windows.VerticalAlignment.Center

            intersect_level = self.doc.GetElement(intersect_res.level_id)
            intersect_level_label = Windows.Controls.Label()
            intersect_level_label.SetValue(Windows.Controls.Grid.ColumnProperty, 1)
            intersect_level_label.Content = intersect_level.Name
            # intersect_level_label.Margin = Windows.Thickness(4, 0, 0, 0)
            intersect_level_label.VerticalAlignment = Windows.VerticalAlignment.Center

            intersect_controllers_stack_panel = Windows.Controls.StackPanel()
            intersect_controllers_stack_panel.SetValue(
                Windows.Controls.Grid.ColumnProperty, 2
            )
            intersect_controllers_stack_panel.Orientation = (
                Windows.Controls.Orientation.Horizontal
            )

            show_intersect_section_box_button = Windows.Controls.Button()
            show_intersect_section_box_button.Content = "Section Box"
            show_intersect_section_box_button.Margin = Windows.Thickness(4)
            show_intersect_section_box_button.Name = "SectionBoxButton_{}_{}".format(
                element_result.mep_element.Id,
                index,
            )
            show_intersect_section_box_button.Style = get_button_style1()
            show_intersect_section_box_button.Click += (
                self.show_intersect_section_box_button_click
            )

            show_intersect_zoom_button = Windows.Controls.Button()
            show_intersect_zoom_button.Content = "Zoom"
            show_intersect_zoom_button.Margin = Windows.Thickness(4)
            show_intersect_zoom_button.Name = "ZoomButton_{}_{}".format(
                element_result.mep_element.Id,
                index,
            )
            show_intersect_zoom_button.Style = get_button_style1()
            show_intersect_zoom_button.Click += self.show_intersect_zoom_button_click

            intersect_controllers_stack_panel.Children.Add(
                show_intersect_section_box_button
            )
            intersect_controllers_stack_panel.Children.Add(show_intersect_zoom_button)

            intersect_grid.Children.Add(intersect_label)
            intersect_grid.Children.Add(intersect_level_label)
            intersect_grid.Children.Add(intersect_controllers_stack_panel)

            mep_and_intersect_stack_panel.Children.Add(intersect_grid)

    def highlight_mep_button_click(self, sender, e):
        try:
            button = sender
            mep_id_int = int(button.Name.split("_")[-1])
            mep_id = ElementId(mep_id_int)
            ids = List[ElementId]([mep_id])
            self.uidoc.Selection.SetElementIds(ids)
            self.uidoc.ShowElements(ids)
        except Exception as e:
            forms.alert(str(e))

    def get_intersect_by_sender(self, sender):
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

        return intersect_res

    def show_intersect_section_box_button_click(self, sender, e):
        try:
            intersect_res = self.get_intersect_by_sender(sender)
            if intersect_res is None:
                return

            bbox_min_point, bbox_max_point = get_min_max_points_from_bbox(
                intersect_res.intersect_bounding_box, intersect_res.transform
            )
            min_max_points_dict = {
                "Min": {
                    "X": bbox_min_point.X,
                    "Y": bbox_min_point.Y,
                    "Z": bbox_min_point.Z,
                },
                "Max": {
                    "X": bbox_max_point.X,
                    "Y": bbox_max_point.Y,
                    "Z": bbox_max_point.Z,
                },
            }
            ex_event_file = ExternalEventDataFile(self.doc)
            ex_event_file.set_key_value("min_max_points_dict", min_max_points_dict)

            show_bbox_3d_event.Raise()
        except Exception as e:
            forms.alert(str(e))

    def show_intersect_zoom_button_click(self, sender, e):
        try:
            ui_view = get_ui_view(self.uidoc)
            if not ui_view:
                self.Hide()
                forms.alert("Please select a view")
                self.Show()
                return

            intersect_res = self.get_intersect_by_sender(sender)
            if intersect_res is None:
                return

            bbox_min_point, bbox_max_point = get_min_max_points_from_bbox(
                intersect_res.intersect_bounding_box, intersect_res.transform
            )

            zoom_increment = 0.8
            zoom_viewCorner1 = bbox_min_point.Add(
                XYZ(-zoom_increment, -zoom_increment, -zoom_increment)
            )
            zoom_viewCorner2 = bbox_max_point.Add(
                XYZ(zoom_increment, zoom_increment, zoom_increment)
            )
            ui_view.ZoomAndCenterRectangle(zoom_viewCorner1, zoom_viewCorner2)
        except Exception as e:
            forms.alert(str(e))

    def render_results(self):
        self.filter_results()
        self.sort_results()

        self.clear_results()

        for index, res in enumerate(self.res_current):
            # if (
            #     index == 0
            #     or res.found_in_level_id
            #     != self.res_current[index - 1].found_in_level_id
            # ):
            #     self.add_level(res.found_in_level_id)

            self.add_result(res)
