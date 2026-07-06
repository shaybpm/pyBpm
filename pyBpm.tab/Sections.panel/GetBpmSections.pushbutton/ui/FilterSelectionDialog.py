# -*- coding: utf-8 -*-
""" Modal window to pick the compilation-model discipline filters.

Groups the filters by discipline (an Expander per group) with a checkbox per
filter and per-group "select / clear" buttons, plus global select/clear and
OK/Cancel. Returns the list of selected ParameterFilterElements (or None on
cancel) via show_dialog().

IronPython 2.7 / WPF - mirrors the FiltersInViewsDialog pattern. """

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from RevitUtils import getElementIdValue, getElementName
from pyrevit.framework import wpf
import os

xaml_file = os.path.join(os.path.dirname(__file__), "FilterSelectionDialog.xaml")


class FilterSelectionDialog(Windows.Window):
    def __init__(self, comp_doc, groups, preselected_ids):
        wpf.LoadComponent(self, xaml_file)
        self.comp_doc = comp_doc
        self.groups = groups
        self.preselected_ids = preselected_ids  # set of int filter ids

        # result: list of selected filters, or None on cancel
        self.selected_filters = None
        # every (checkbox, filter) pair across all groups
        self.all_pairs = []

        self.build_groups()

    def build_groups(self):
        for group in self.groups:
            expander = Windows.Controls.Expander()
            expander.IsExpanded = True
            expander.Margin = Windows.Thickness(0, 0, 0, 6)
            expander.Header = u"{} ({})".format(
                group["display"], len(group["filters"])
            )

            content = Windows.Controls.StackPanel()

            # this group's checkboxes (captured by the per-group button handlers)
            group_checkboxes = []

            btn_row = Windows.Controls.StackPanel()
            btn_row.Orientation = Windows.Controls.Orientation.Horizontal
            btn_row.Margin = Windows.Thickness(0, 0, 0, 4)

            select_group_btn = Windows.Controls.Button()
            select_group_btn.Content = u"סמן קבוצה"
            select_group_btn.Margin = Windows.Thickness(0, 0, 4, 0)
            select_group_btn.Padding = Windows.Thickness(6, 1, 6, 1)
            select_group_btn.Click += self.make_group_handler(group_checkboxes, True)

            clear_group_btn = Windows.Controls.Button()
            clear_group_btn.Content = u"נקה קבוצה"
            clear_group_btn.Padding = Windows.Thickness(6, 1, 6, 1)
            clear_group_btn.Click += self.make_group_handler(group_checkboxes, False)

            btn_row.Children.Add(select_group_btn)
            btn_row.Children.Add(clear_group_btn)
            content.Children.Add(btn_row)

            for f in group["filters"]:
                checkbox = Windows.Controls.CheckBox()
                checkbox.Content = getElementName(f)
                checkbox.Margin = Windows.Thickness(0, 2, 0, 2)
                fid = getElementIdValue(self.comp_doc, f.Id)
                checkbox.IsChecked = fid in self.preselected_ids
                content.Children.Add(checkbox)
                group_checkboxes.append(checkbox)
                self.all_pairs.append((checkbox, f))

            expander.Content = content
            self.groups_panel.Children.Add(expander)

    def make_group_handler(self, checkboxes, check):
        def handler(sender, e):
            for checkbox in checkboxes:
                checkbox.IsChecked = check

        return handler

    def select_all_click(self, sender, e):
        for checkbox, f in self.all_pairs:
            checkbox.IsChecked = True

    def clear_all_click(self, sender, e):
        for checkbox, f in self.all_pairs:
            checkbox.IsChecked = False

    def ok_btn_click(self, sender, e):
        selected = [f for checkbox, f in self.all_pairs if checkbox.IsChecked]
        if not selected:
            Windows.MessageBox.Show(
                u"יש לבחור לפחות פילטר אחד.", u"בחירת פילטרים"
            )
            return
        self.selected_filters = selected
        self.Close()

    def cancel_btn_click(self, sender, e):
        self.selected_filters = None
        self.Close()

    def show_dialog(self):
        self.ShowDialog()
        return self.selected_filters
