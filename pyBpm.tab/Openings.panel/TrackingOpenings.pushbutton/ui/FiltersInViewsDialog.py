# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from ServerUtils import get_project_openings_filter001
from RevitUtilsOpenings import get_specific_openings_filter
from Autodesk.Revit.DB import FilteredElementCollector, View, ViewType, ElementId
from pyrevit.framework import wpf
import os

xaml_file = os.path.join(os.path.dirname(__file__), "FiltersInViewsDialogUi.xaml")


class FiltersInViewsDialog(Windows.Window):
    def __init__(self, doc):
        wpf.LoadComponent(self, xaml_file)
        self.doc = doc
        self.values_to_return = None
        self.view_types = [
            ViewType.FloorPlan,
            ViewType.CeilingPlan,
            ViewType.Section,
            ViewType.Elevation,
            ViewType.ThreeD,
            ViewType.EngineeringPlan,
        ]
        self.specific_openings_filter = get_specific_openings_filter(doc)
        self.views_app = self.get_views_app()
        self.update_views_app_when_check_uncheck_item = True

        self.db_project_openings = get_project_openings_filter001(doc)
        self.filter_description_textblock.Text = (
            "יש {} פתחים לא מאושרים בפרויקט".format(
                len(self.db_project_openings) if self.db_project_openings else 0
            )
        )

        self.initial_view_type_combo_box()
        self.render()

    def get_views_app(self):
        views_app = []
        for view in FilteredElementCollector(self.doc).OfClass(View).ToElements():
            if view.ViewType not in self.view_types:
                continue
            if (
                not view.IsTemplate
                and view.ViewTemplateId != ElementId.InvalidElementId
            ):
                continue
            apply = self.is_apply_init(view)
            views_app.append({"view": view, "apply": apply})
        return views_app

    def initial_view_type_combo_box(self):
        dash = "-"
        options = [dash]
        for view_type in self.view_types:
            options.append(view_type.ToString())
        for view_type in options:
            self.view_type_combobox.Items.Add(view_type)
        self.view_type_combobox.SelectedItem = dash

    def render(self):
        self.views_listbox.Items.Clear()
        for view_app in self.views_app:
            view = view_app["view"]
            if (
                self.view_name_textbox.Text != ""
                and self.view_name_textbox.Text.lower() not in view.Name.lower()
            ):
                continue
            if (
                self.view_type_combobox.SelectedItem is not None
                and self.view_type_combobox.SelectedItem != "-"
                and view.ViewType.ToString() != self.view_type_combobox.SelectedItem
            ):
                continue
            self.views_listbox.Items.Add(
                ViewListBoxItem(view, view_app["apply"], self.check_uncheck_item)
            )

    def is_apply_init(self, view):
        return (
            self.specific_openings_filter is not None
            and view.IsFilterApplied(self.specific_openings_filter.Id)
            and not view.GetFilterVisibility(self.specific_openings_filter.Id)
        )

    def view_name_textbox_TextChanged(self, sender, e):
        self.render()

    def view_type_combobox_SelectionChanged(self, sender, e):
        self.render()

    def cancel_btn_click(self, sender, e):
        self.Close()

    def check_or_uncheck_all(self, check):
        self.update_views_app_when_check_uncheck_item = False
        for item in self.views_listbox.Items:
            if isinstance(item, ViewListBoxItem):
                item.apply_checkbox.IsChecked = check
        self.update_views_app_when_check_uncheck_item = True
        self.update_views_app()

    def get_view_app(self, view_id):
        for view_app in self.views_app:
            if view_app["view"].Id == view_id:
                return view_app
        return None

    def update_views_app(self):
        new_views_app = []
        for i in self.views_listbox.Items:
            if not isinstance(i, ViewListBoxItem):
                continue
            view_app = self.get_view_app(i.view.Id)
            if view_app is None:
                continue
            new_views_app.append(
                {
                    "view": i.view,
                    "apply": i.apply_checkbox.IsChecked,
                }
            )
        self.views_app = new_views_app

    def check_uncheck_item(self, item, check):
        if item.IsSelected:
            for i in self.views_listbox.Items:
                if not isinstance(i, ViewListBoxItem):
                    continue
                if not i.IsSelected:
                    continue
                if i.view.Id == item.view.Id:
                    continue
                i.apply_checkbox.IsChecked = check

        if self.update_views_app_when_check_uncheck_item:
            self.update_views_app()

    def check_all_click(self, sender, e):
        self.check_or_uncheck_all(True)

    def uncheck_all_click(self, sender, e):
        self.check_or_uncheck_all(False)

    def get_openings_result(self):
        return [
            {"discipline": x["discipline"], "mark": x["mark"]}
            for x in self.db_project_openings
        ]

    def get_views_result(self):
        views_res = []
        for view_app in self.views_app:
            views_res.append(
                {
                    "view_id": view_app["view"].Id.IntegerValue,
                    "apply": view_app["apply"],
                }
            )
        return views_res

    def ok_btn_click(self, sender, e):
        self.values_to_return = {
            "openings": self.get_openings_result(),
            "views": self.get_views_result(),
        }
        self.Close()

    def show_dialog(self):
        self.ShowDialog()
        return self.values_to_return


class ViewListBoxItem(Windows.Controls.ListBoxItem):
    def __init__(self, view, init_apply, check_uncheck_func):
        self.view = view
        self.init_apply = init_apply
        self.check_uncheck_func = check_uncheck_func

        self.render()

    def get_text(self):
        text = self.view.Name
        if self.view.IsTemplate:
            text += " (Template)"
        return text

    def render(self):
        self.main_grid = Windows.Controls.Grid()
        # 2 columns
        col0 = Windows.Controls.ColumnDefinition()
        col0.Width = Windows.GridLength(300)
        col1 = Windows.Controls.ColumnDefinition()
        col1.Width = Windows.GridLength.Auto
        self.main_grid.ColumnDefinitions.Add(col0)
        self.main_grid.ColumnDefinitions.Add(col1)
        # col 0 - name
        self.name_text_block = Windows.Controls.TextBlock()
        self.name_text_block.Text = self.get_text()
        # col 1 - apply checkbox
        self.apply_checkbox = Windows.Controls.CheckBox()
        self.apply_checkbox.IsChecked = self.init_apply
        self.apply_checkbox.Checked += self.apply_checked
        self.apply_checkbox.Unchecked += self.apply_unchecked
        # add to grid
        self.main_grid.Children.Add(self.name_text_block)
        self.main_grid.Children.Add(self.apply_checkbox)
        # set column
        Windows.Controls.Grid.SetColumn(self.name_text_block, 0)
        Windows.Controls.Grid.SetColumn(self.apply_checkbox, 1)
        # add to listbox item
        self.Content = self.main_grid

    def apply_checked(self, sender, e):
        self.check_uncheck_func(self, True)

    def apply_unchecked(self, sender, e):
        self.check_uncheck_func(self, False)
