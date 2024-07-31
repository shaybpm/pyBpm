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

from pyrevit import forms

from Autodesk.Revit.DB import ElementId, XYZ

from RevitUtils import get_min_max_points_from_bbox, get_ui_view, get_all_link_instances
from RevitUtilsOpenings import (
    get_all_openings_include_links,
    get_opening_discipline_and_number,
)
from UiUtils import get_button_style1

from EventHandlers import show_opening_3d_event
from ExternalEventDataFile import ExternalEventDataFile

xaml_file = os.path.join(os.path.dirname(__file__), "OpeningExplorerDialogUi.xaml")


class OpeningExplorerDialog(Windows.Window):
    def __init__(self, uidoc):
        wpf.LoadComponent(self, xaml_file)

        self.uidoc = uidoc
        self.doc = self.uidoc.Document
        self.openings = get_all_openings_include_links(self.doc)
        self.rendered_openings = None
        self.render_openings()

    def get_rendered_openings(self):
        discipline_user_input = self.DisciplineFilterTextBox.Text
        number_user_input = self.NumberFilterTextBox.Text

        rendered_openings = []
        for opening_dict in self.openings:
            for opening in opening_dict["elements"]:
                opening_discipline, opening_number = get_opening_discipline_and_number(
                    opening
                )
                if opening_discipline is None:
                    opening_discipline = str(opening_discipline)
                if opening_number is None:
                    opening_number = str(opening_number)

                if (
                    discipline_user_input
                    and discipline_user_input not in opening_discipline
                ):
                    continue
                if number_user_input and number_user_input not in opening_number:
                    continue
                bbox = opening.get_BoundingBox(None)
                if not bbox:
                    continue
                transform = (
                    opening_dict["link"].GetTotalTransform()
                    if opening_dict["link"]
                    else None
                )
                bbox_min_point, bbox_max_point = get_min_max_points_from_bbox(
                    bbox, transform
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
                rendered_openings.append(
                    {
                        "opening_discipline": opening_discipline,
                        "opening_number": opening_number,
                        "min_max_points": min_max_points_dict,
                    }
                )

        rendered_openings.sort(
            key=lambda x: (
                x["opening_discipline"],
                (
                    int(x["opening_number"])
                    if x["opening_number"].isdigit()
                    else x["opening_number"]
                ),
            )
        )

        return rendered_openings

    def render_openings(self):
        rendered_openings = self.get_rendered_openings()
        self.rendered_openings = rendered_openings

        main_stack_panel = self.StackPanelMain
        main_stack_panel.Children.Clear()

        for index, opening in enumerate(rendered_openings):
            opening_grid = Windows.Controls.Grid()
            col_def1 = Windows.Controls.ColumnDefinition()
            col_def1.Width = Windows.GridLength(40)
            col_def2 = Windows.Controls.ColumnDefinition()
            col_def2.Width = Windows.GridLength(40)
            col_def3 = Windows.Controls.ColumnDefinition()
            opening_grid.ColumnDefinitions.Add(col_def1)
            opening_grid.ColumnDefinitions.Add(col_def2)
            opening_grid.ColumnDefinitions.Add(col_def3)

            opening_discipline_label = Windows.Controls.Label()
            opening_discipline_label.Content = opening["opening_discipline"]
            opening_discipline_label.SetValue(Windows.Controls.Grid.ColumnProperty, 0)
            opening_grid.Children.Add(opening_discipline_label)

            opening_number_label = Windows.Controls.Label()
            opening_number_label.Content = opening["opening_number"]
            opening_number_label.SetValue(Windows.Controls.Grid.ColumnProperty, 1)
            opening_grid.Children.Add(opening_number_label)

            opening_controls_stack_panel = Windows.Controls.StackPanel()
            opening_controls_stack_panel.Orientation = (
                Windows.Controls.Orientation.Horizontal
            )
            opening_controls_stack_panel.SetValue(
                Windows.Controls.Grid.ColumnProperty, 2
            )
            opening_grid.Children.Add(opening_controls_stack_panel)

            opening_zoom_button = Windows.Controls.Button()
            opening_zoom_button.Content = "Zoom"
            opening_zoom_button.Tag = index
            opening_zoom_button.Style = get_button_style1()
            opening_zoom_button.Click += self.opening_zoom_button_click
            opening_controls_stack_panel.Children.Add(opening_zoom_button)

            opening_3d_button = Windows.Controls.Button()
            opening_3d_button.Content = "3D"
            opening_3d_button.Tag = index
            opening_3d_button.Style = get_button_style1()
            opening_3d_button.Click += self.opening_3d_button_click
            opening_controls_stack_panel.Children.Add(opening_3d_button)

            main_stack_panel.Children.Add(opening_grid)

    def opening_zoom_button_click(self, sender, e):
        ui_view = get_ui_view(self.uidoc)
        if not ui_view:
            self.Hide()
            forms.alert("Please select a view")
            self.Show()
            return

        opening = self.rendered_openings[sender.Tag]

        zoom_increment = 0.8
        zoom_viewCorner1 = XYZ(
            opening["min_max_points"]["Min"]["X"],
            opening["min_max_points"]["Min"]["Y"],
            opening["min_max_points"]["Min"]["Z"],
        ).Subtract(XYZ(zoom_increment, zoom_increment, zoom_increment))

        zoom_viewCorner2 = XYZ(
            opening["min_max_points"]["Max"]["X"],
            opening["min_max_points"]["Max"]["Y"],
            opening["min_max_points"]["Max"]["Z"],
        ).Add(XYZ(zoom_increment, zoom_increment, zoom_increment))
        ui_view.ZoomAndCenterRectangle(zoom_viewCorner1, zoom_viewCorner2)

    def opening_3d_button_click(self, sender, e):
        opening = self.rendered_openings[sender.Tag]

        ex_event_file = ExternalEventDataFile(self.doc)
        ex_event_file.set_key_value("min_max_points_dict", opening["min_max_points"])

        show_opening_3d_event.Raise()

    def filter_selection_changed(self, sender, e):
        self.render_openings()
