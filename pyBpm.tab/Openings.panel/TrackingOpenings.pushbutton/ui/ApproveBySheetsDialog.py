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

from pyUtils import safe_int

xaml_file = os.path.join(os.path.dirname(__file__), "ApproveBySheetsDialogUi.xaml")


class ApproveBySheetsDialog(Windows.Window):
    def __init__(self, data):
        wpf.LoadComponent(self, xaml_file)
        self.data = data
        self.result = None  # list of dicts with: `uniqueId`, `discipline`, `mark`, `approved` and the `new_approved_status`.

        self.modelTitleTextBlock.Text = "שם מודל הקומפילציה: " + self.data.get(
            "modelTitle", "Unknown Model"
        )

        self.openings = None  # type: list | None

        self.initialize_sheet_tree_view_container_StackPanel()

    def initialize_sheet_tree_view_container_StackPanel(self):
        for sheet in sorted(
            self.data.get("sheets", []),
            key=lambda x: int(x.get("number", "9999")),
        ):
            sheet_tree_view_item = Windows.Controls.TreeViewItem()
            sheet_tree_view_item.Header = sheet.get("title", "-- No Title --")
            for revision in sheet.get("revisions", []):
                revision_tree_view_item = Windows.Controls.TreeViewItem()
                revision_data = revision.get("revisionData", {})

                revision_tree_view_item_header_grid = Windows.Controls.Grid()
                revision_tree_view_item_header_grid.ColumnDefinitions.Add(
                    Windows.Controls.ColumnDefinition(Width=Windows.GridLength(380))
                )
                revision_tree_view_item_header_grid.ColumnDefinitions.Add(
                    Windows.Controls.ColumnDefinition(
                        Width=Windows.GridLength(1, Windows.GridUnitType.Auto)
                    )
                )
                revision_tree_view_item_header_grid.ColumnDefinitions.Add(
                    Windows.Controls.ColumnDefinition(Width=Windows.GridLength(120))
                )

                rev_name_textBlock = Windows.Controls.TextBlock()
                rev_name_textBlock_text = revision_data.get(
                    "name", "-- No Revision Name --"
                )
                rev_name_textBlock.Text = rev_name_textBlock_text
                rev_name_textBlock.ToolTip = rev_name_textBlock_text
                rev_name_textBlock.SetValue(Windows.Controls.Grid.ColumnProperty, 0)
                revision_tree_view_item_header_grid.Children.Add(rev_name_textBlock)

                separator_border = Windows.Controls.Border()
                separator_border.SetValue(Windows.Controls.Grid.ColumnProperty, 1)
                separator_border.BorderThickness = Windows.Thickness(0, 0, 1, 0)
                separator_border.BorderBrush = Windows.Media.Brushes.Gray
                separator_border.Margin = Windows.Thickness(5, 0, 5, 0)
                revision_tree_view_item_header_grid.Children.Add(separator_border)

                rev_date_textBlock = Windows.Controls.TextBlock()
                rev_date_textBlock_text = revision_data.get("date", "-- No Date --")
                rev_date_textBlock.Text = rev_date_textBlock_text
                rev_date_textBlock.ToolTip = rev_date_textBlock_text
                rev_date_textBlock.SetValue(Windows.Controls.Grid.ColumnProperty, 2)
                revision_tree_view_item_header_grid.Children.Add(rev_date_textBlock)

                revision_tree_view_item.Header = revision_tree_view_item_header_grid

                revision_tree_view_item.Tag = revision_data.get("uniqueId", "NO_UID")
                revision_tree_view_item.MouseDoubleClick += (
                    self.double_click_rev_tree_view_item
                )
                sheet_tree_view_item.Items.Add(revision_tree_view_item)
            self.tree_view.Items.Add(sheet_tree_view_item)

    def get_openings_by_revision_uid(self, revision_uid):
        if not revision_uid or revision_uid == "NO_UID":
            return []
        for sheet in self.data.get("sheets", []):
            for revision in sheet.get("revisions", []):
                if revision.get("revisionData", {}).get("uniqueId") == revision_uid:
                    return revision.get("openings", [])

    def double_click_rev_tree_view_item(self, sender, e):
        openings = self.get_openings_by_revision_uid(sender.Tag)
        if not openings:
            Windows.MessageBox.Show(
                "לא נמצאו פתחים במהדורה זו.",
                "אין פתחים",
                Windows.MessageBoxButton.OK,
                Windows.MessageBoxImage.Information,
            )
            return
        self.go_to_next_step(openings)

    def go_to_next_step(self, openings):
        self.openings = openings  # type: list | None
        if self.openings:
            self.openings.sort(
                key=lambda x: (
                    x.get("discipline", ""),
                    safe_int(x.get("mark", ""), 9999),
                )
            )
            for opening in self.openings:
                opening["combo_selected_index"] = 0

        self.ok_btn.IsEnabled = True
        self.tree_view.Visibility = Windows.Visibility.Collapsed
        self.opening_grid.Visibility = Windows.Visibility.Visible
        self.titleTextBlock.Text = "ערוך סטטוס אישורים"
        self.explainTextBlock.Text = "ניתן לבחור מספר שורות ביחד עם לחיצה על Ctrl או Shift, ולערוך את הסטטוס של כל הפתחים שנבחרו."

        self.rerender_opening_listbox()

    def rerender_opening_listbox(self):
        self.opening_listbox.Items.Clear()
        for opening in self.openings:
            if (
                self.opening_filter_textbox.Text != ""
                and self.opening_filter_textbox.Text.upper()
                not in opening.get("mark", "").upper()
                and self.opening_filter_textbox.Text.upper()
                not in opening.get("discipline", "").upper()
            ):
                continue
            item = ListBoxItem(opening, self.combo_selection_changed)
            self.opening_listbox.Items.Add(item)

    def combo_selection_changed(self, opening, index):
        # The goal is to update all the selected items in the listbox
        selected_items = self.opening_listbox.SelectedItems
        if not selected_items:
            return
        # If this opening not in the selected items, do nothing
        opening_unique_id = opening.get("uniqueId")
        if not opening_unique_id:
            return
        all_selected_uids = [item.opening.get("uniqueId") for item in selected_items]
        if opening_unique_id not in all_selected_uids:
            return
        # Update the selected items
        for item in selected_items:
            # turn of the event handler to prevent recursion
            if not item.isEnabled:
                continue
            item.selection_changed_is_on = False
            item.combo_selected_index = index
            item.selection_changed_is_on = True

    def opening_filter_textbox_TextChanged(self, sender, e):
        self.rerender_opening_listbox()

    def ok_btn_click(self, sender, e):
        result = []
        for opening in self.openings:
            new_approved_status_name = ListBoxItem.get_approved_status_name(
                opening["combo_selected_index"]
            )
            if not new_approved_status_name or new_approved_status_name == "-":
                continue
            if not opening.get("uniqueId"):
                continue
            if not opening.get("discipline"):
                continue
            if not opening.get("mark"):
                continue

            result.append(
                {
                    "uniqueId": opening["uniqueId"],
                    "discipline": opening["discipline"],
                    "mark": opening["mark"],
                    "approved": opening.get("approved"),
                    "new_approved_status": new_approved_status_name,
                }
            )
        self.result = result

        self.Close()

    def cancel_btn_click(self, sender, e):
        # Logic for Cancel button click
        self.Close()


class ListBoxItem(Windows.Controls.ListBoxItem):
    def __init__(self, opening, combo_selection_changed):
        super(ListBoxItem, self).__init__()
        self.opening = opening
        self.combo_selection_changed = combo_selection_changed

        self.selection_changed_is_on = True

        self.isEnabled = opening.get("openingDataSynced", False)

        col_def_0 = Windows.Controls.ColumnDefinition(
            Width=Windows.GridLength(1, Windows.GridUnitType.Star)
        )
        col_def_0.Width = Windows.GridLength(40)

        col_def_1 = Windows.Controls.ColumnDefinition(
            Width=Windows.GridLength(1, Windows.GridUnitType.Star)
        )
        col_def_1.Width = Windows.GridLength(40)

        col_def_2 = Windows.Controls.ColumnDefinition(
            Width=Windows.GridLength(1, Windows.GridUnitType.Star)
        )
        col_def_2.Width = Windows.GridLength(200)

        col_def_3 = Windows.Controls.ColumnDefinition(
            Width=Windows.GridLength(1, Windows.GridUnitType.Star)
        )
        col_def_3.Width = Windows.GridLength(200)

        grid = Windows.Controls.Grid()
        grid.ColumnDefinitions.Add(col_def_0)
        grid.ColumnDefinitions.Add(col_def_1)
        grid.ColumnDefinitions.Add(col_def_2)
        grid.ColumnDefinitions.Add(col_def_3)

        discipline_text = opening.get("discipline", "-")
        discipline_textBlock = Windows.Controls.TextBlock(Text=discipline_text)
        discipline_textBlock.ToolTip = discipline_text
        discipline_textBlock.Margin = Windows.Thickness(0, 0, 5, 0)
        discipline_textBlock.SetValue(Windows.Controls.Grid.ColumnProperty, 0)

        mark_text = opening.get("mark", "-")
        mark_textBlock = Windows.Controls.TextBlock(Text=mark_text)
        mark_textBlock.ToolTip = mark_text
        mark_textBlock.Margin = Windows.Thickness(0, 0, 5, 0)
        mark_textBlock.SetValue(Windows.Controls.Grid.ColumnProperty, 1)

        current_approved_text = opening.get("approved", "-")
        current_approved_textBlock = Windows.Controls.TextBlock(
            Text=current_approved_text
        )
        ap_status_option = self.get_approval_status_option_by_name(
            current_approved_text
        )
        if ap_status_option:
            current_approved_textBlock.Background = ap_status_option["bg"]
        current_approved_textBlock.ToolTip = current_approved_text
        current_approved_textBlock.Margin = Windows.Thickness(0, 0, 5, 0)
        current_approved_textBlock.SetValue(Windows.Controls.Grid.ColumnProperty, 2)

        new_approved_combo = Windows.Controls.ComboBox()
        for option_dict in ListBoxItem.approval_status_options:
            option_name = option_dict["name"]
            combo_item = Windows.Controls.ComboBoxItem()
            combo_item.Content = option_name
            new_approved_combo.Items.Add(combo_item)
        new_approved_combo.SelectedIndex = opening["combo_selected_index"]
        new_approved_combo.SelectionChanged += self.handle_combo_selection_change
        new_approved_combo.Margin = Windows.Thickness(0, 0, 5, 0)
        new_approved_combo.SetValue(Windows.Controls.Grid.ColumnProperty, 3)
        new_approved_combo.IsEnabled = self.isEnabled
        self._comb = new_approved_combo

        grid.Children.Add(discipline_textBlock)
        grid.Children.Add(mark_textBlock)
        grid.Children.Add(current_approved_textBlock)
        grid.Children.Add(new_approved_combo)

        self.Content = grid

    @property
    def combo_selected_index(self):
        return self._comb.SelectedIndex

    @combo_selected_index.setter
    def combo_selected_index(self, value):
        self._comb.SelectedIndex = value

    def handle_combo_selection_change(self, sender, e):
        self.opening["combo_selected_index"] = sender.SelectedIndex
        if not self.selection_changed_is_on:
            return
        self.combo_selection_changed(self.opening, self.combo_selected_index)

    def get_approval_status_option_by_name(self, name):
        for option in ListBoxItem.approval_status_options:
            if option["name"] == name:
                return option
        return None

    # Static property
    approval_status_options = [
        {"name": "-", "bg": Windows.Media.Brushes.LightGray},
        {"name": "approved", "bg": Windows.Media.Brushes.LightGreen},
        {"name": "not approved", "bg": Windows.Media.Brushes.LightPink},
        {"name": "conditionally approved", "bg": Windows.Media.Brushes.LightBlue},
    ]

    @staticmethod
    def get_approved_status_name(combo_selected_index):
        if combo_selected_index < 0 or combo_selected_index >= len(
            ListBoxItem.approval_status_options
        ):
            raise ValueError(
                "Invalid combo_selected_index: {}".format(combo_selected_index)
            )
        return ListBoxItem.approval_status_options[combo_selected_index]["name"]
