# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from Autodesk.Revit.DB import ElementId, XYZ

from System import Uri
from System import Windows
from pyrevit.framework import wpf
import os
import json

from ServerUtils import get_bonds
from RevitUtils import (
    get_model_guid_title_map,
    get_min_max_points_from_bbox,
    get_link_by_model_guid,
    get_ui_view,
)
from ReusableExternalEvents import show_bbox_3d_event
from ExternalEventDataFile import ExternalEventDataFile

xaml_file = os.path.join(os.path.dirname(__file__), "BondsViewerUi.xaml")

bonds_display_config = [
    # {"key": "Id", "Size": "120", "Title": "Id"},
    # {"key": "BondId", "Size": "120", "Title": "BondId"},
    {"key": "SequenceNo", "Size": "40", "Title": "#"},
    {"key": "Title", "Size": "120", "Title": "Title"},
    {"key": "Description", "Size": "120", "Title": "Description"},
    # {"key": "Project", "Size": "120", "Title": "Project"},
    {"key": "Suggestion", "Size": "120", "Title": "Suggestion"},
    {"key": "PictureUrl", "Size": "120", "Title": "Picture"},
    {"key": "CreatedBy", "Size": "160", "Title": "Created By"},
    {"key": "AssignedTo", "Size": "160", "Title": "Assigned To"},
    {"key": "Status", "Size": "120", "Title": "Status"},
    {"key": "Answer", "Size": "120", "Title": "Answer"},
    # {"key": "AnswerDate", "Size": "120", "Title": "AnswerDate"},
    {"key": "LocationX", "Size": "40", "Title": "X"},
    {"key": "LocationNo", "Size": "40", "Title": "Y"},
    {"key": "Level", "Size": "120", "Title": "Level"},
    {"key": "Priority", "Size": "52", "Title": "Priority"},
    {"key": "Type", "Size": "120", "Title": "Type"},
    # {"key": "CreatedDate", "Size": "120", "Title": "CreatedDate"},
    # {"key": "RevitUserId", "Size": "120", "Title": "RevitUserId"},
    # {"key": "ReadStatus", "Size": "120", "Title": "ReadStatus"},
    # {"key": "ShowNotificationToUser", "Size": "120", "Title": "ShowNotificationToUser"},
    # {"key": "CloudProjectGuid", "Size": "120", "Title": "CloudProjectGuid"},
]


class BondsViewerUI(Windows.Window):
    def __init__(self, uidoc):
        wpf.LoadComponent(self, xaml_file)
        self.uidoc = uidoc
        self.doc = uidoc.Document
        self.model_guid_title_map = get_model_guid_title_map(self.doc)
        self._bonds = []
        self.txt_filter = ""
        self.initial_headers()
        self.fetch_bonds()

    @property
    def bonds(self):
        return self._bonds

    @bonds.setter
    def bonds(self, value):
        self._bonds = sorted(
            value,
            key=lambda b: b.get("SequenceNo", 9999),
        )
        self.initialize_table()

    def initial_headers(self):
        self.headers_StackPanel.Children.Clear()
        for props in bonds_display_config:
            tb = Windows.Controls.TextBlock()
            tb.Text = props["Title"]
            tb.Width = float(props["Size"]) - 2
            tb.Margin = Windows.Thickness(2, 0, 0, 0)
            self.headers_StackPanel.Children.Add(tb)

    def fetch_bonds(self):
        try:
            self.bonds = get_bonds(self.doc)
        except Exception as e:
            print(e)

    def TxtBondsFilter_TextBox_TextChanged(self, sender, e):
        self.txt_filter = sender.Text.strip().lower()
        self.initialize_table()

    def is_bond_visible(self, bond):
        for key_dict in bonds_display_config:
            key = key_dict["key"]
            if key not in bond:
                continue
            bond_value = bond[key]
            bond_value = (
                bond_value
                if key != "CreatedBy" and key != "AssignedTo"
                else self.model_guid_title_map.get(bond_value, "Unknown")
            )
            if self.txt_filter == "" or (
                key in bond and self.txt_filter in str(bond_value).lower()
            ):
                return True

        return False

    def initialize_table(self):
        self.bonds_ListBox.Items.Clear()

        for bond in self.bonds:
            if not self.is_bond_visible(bond):
                continue
            item = BondsListBoxItem(bond, self.model_guid_title_map)
            self.bonds_ListBox.Items.Add(item)

    def get_selected_bond_bbox(self):
        selected_item = self.bonds_ListBox.SelectedItem
        if not selected_item:
            return None, None
        bond = selected_item.bond
        if not bond:
            return None, None
        created_by = bond.get("CreatedBy")
        if not created_by:
            return None, None

        _doc = None
        _transform = None
        if (
            self.doc.IsModelInCloud
            and self.doc.GetCloudModelPath().GetModelGUID().ToString() == created_by
        ):
            _doc = self.doc
        else:
            link = get_link_by_model_guid(self.doc, created_by)
            if not link:
                Windows.MessageBox.Show(
                    "No link found for the selected bond's CreatedBy model.",
                    "Error",
                    Windows.MessageBoxButton.OK,
                    Windows.MessageBoxImage.Error,
                )
                return None, None
            link_doc = link.GetLinkDocument()
            if not link_doc:
                Windows.MessageBox.Show(
                    "Link document is not loaded.",
                    "Error",
                    Windows.MessageBoxButton.OK,
                    Windows.MessageBoxImage.Error,
                )
                return None, None
            _transform = link.GetTotalTransform()
            _doc = link_doc

        if not _doc:
            Windows.MessageBox.Show(
                "Document not found for the selected bond.",
                "Error",
                Windows.MessageBoxButton.OK,
                Windows.MessageBoxImage.Error,
            )
            return None, None

        bond_id = bond.get("BondId")
        # Convert bond_id to int if it's a string of digits
        if isinstance(bond_id, str) and bond_id.isdigit():
            bond_id = int(bond_id)
        if not bond_id or not isinstance(bond_id, int):
            Windows.MessageBox.Show(
                "BondId is missing or invalid.",
                "Error",
                Windows.MessageBoxButton.OK,
                Windows.MessageBoxImage.Error,
            )
            return None, None
        bond_elem = _doc.GetElement(ElementId(bond_id))
        if (
            not bond_elem
            or not bond_elem.Category
            or bond_elem.Category.Name != "Generic Models"
        ):
            Windows.MessageBox.Show(
                "Bond with ID {} not found.".format(bond_id),
                "Error",
                Windows.MessageBoxButton.OK,
                Windows.MessageBoxImage.Error,
            )
            return None, None
        bbox = bond_elem.get_BoundingBox(None)
        if not bbox:
            Windows.MessageBox.Show(
                "Bounding box for bond with ID {} is not available.".format(bond_id),
                "Error",
                Windows.MessageBoxButton.OK,
                Windows.MessageBoxImage.Error,
            )
            return None, None
        return get_min_max_points_from_bbox(bbox, _transform)

    def section_box_btn_Click(self, sender, e):
        try:
            bbox_min_point, bbox_max_point = self.get_selected_bond_bbox()
            if bbox_min_point is None or bbox_max_point is None:
                return

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
            print(e)

    def zoom_btn_Click(self, sender, e):
        try:
            ui_view = get_ui_view(self.uidoc)
            if not ui_view:
                self.Hide()
                Windows.MessageBox.Show(
                    "No view found.",
                    "Error",
                    Windows.MessageBoxButton.OK,
                    Windows.MessageBoxImage.Error,
                )
                return

            bbox_min_point, bbox_max_point = self.get_selected_bond_bbox()
            if bbox_min_point is None or bbox_max_point is None:
                return

            zoom_increment = 0.8
            zoom_viewCorner1 = bbox_min_point.Add(
                XYZ(-zoom_increment, -zoom_increment, -zoom_increment)
            )
            zoom_viewCorner2 = bbox_max_point.Add(
                XYZ(zoom_increment, zoom_increment, zoom_increment)
            )
            ui_view.ZoomAndCenterRectangle(zoom_viewCorner1, zoom_viewCorner2)
        except Exception as e:
            print(e)

    def refresh_btn_Click(self, sender, e):
        self.fetch_bonds()


class BondsListBoxItem(Windows.Controls.ListBoxItem):
    def __init__(self, bond, model_guid_title_map):
        self.bond = bond
        self.model_guid_title_map = model_guid_title_map

        self.initialize_row()

    def initialize_row(self):
        grid = Windows.Controls.Grid()
        for idx, key_dict in enumerate(bonds_display_config):
            key = key_dict["key"]
            size = key_dict["Size"]
            col = Windows.Controls.ColumnDefinition()
            col.Width = Windows.GridLength(float(size))
            grid.ColumnDefinitions.Add(col)

        for idx, key_dict in enumerate(bonds_display_config):
            key = key_dict["key"]
            if key not in self.bond:
                continue
            if key == "PictureUrl":
                if self.bond.get(key):
                    img = Windows.Controls.Image()
                    # Convert Uri to BitmapImage for ImageSource
                    from System.Windows.Media.Imaging import BitmapImage

                    bitmap = BitmapImage()
                    bitmap.BeginInit()
                    bitmap.UriSource = Uri(self.bond[key])
                    bitmap.EndInit()
                    img.Source = bitmap
                    img.Width = 100
                    img.Height = 100
                    img.Margin = Windows.Thickness(2)
                    Windows.Controls.Grid.SetColumn(img, idx)
                    grid.Children.Add(img)
                continue

            value = str(self.bond.get(key, ""))
            tb = Windows.Controls.TextBlock()
            tb.TextWrapping = Windows.TextWrapping.Wrap
            tb.Text = (
                value
                if key != "CreatedBy" and key != "AssignedTo"
                else self.model_guid_title_map.get(value, "Unknown")
            )
            tb.Margin = Windows.Thickness(9, 0, 0, 0)
            Windows.Controls.Grid.SetColumn(tb, idx)
            grid.Children.Add(tb)

        border = Windows.Controls.Border()
        border.BorderThickness = Windows.Thickness(0, 0, 0, 2)
        border.BorderBrush = Windows.Media.Brushes.LightGray
        border.Margin = Windows.Thickness(0, 0, 0, 2)
        border.Child = grid

        self.Content = border
