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

xaml_file = os.path.join(os.path.dirname(__file__), "ApproveBySheetsDialogUi.xaml")


class ApproveBySheetsDialogResult:
    def __init__(self, openings, new_approved_status):
        # openings should be a list of dicts with: uniqueId, discipline, and mark
        # new_approved_status should be a list of dicts with: uniqueId and approved
        self.openings = openings
        self.new_approved_status = new_approved_status


class ApproveBySheetsDialog(Windows.Window):
    def __init__(self, data):
        wpf.LoadComponent(self, xaml_file)
        self.data = data
        self.result = None  # type: ApproveBySheetsDialogResult | None

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
        self.openings = openings
        self.ok_btn.IsEnabled = True
        self.tree_view.Visibility = Windows.Visibility.Collapsed
        self.opening_grid.Visibility = Windows.Visibility.Visible
        self.titleTextBlock.Text = "ערוך סטטוס אישורים"
        self.explainTextBlock.Text = "ניתן לבחור מספר שורות ביחד עם לחיצה על Ctrl או Shift, ולערוך את הסטטוס של כל הפתחים שנבחרו."

        self.opening_listbox.Items.Clear()
        for opening in openings:
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
            item.selection_changed_is_on = False
            item.combo_selected_index = index
            item.selection_changed_is_on = True

    def ok_btn_click(self, sender, e):
        # Logic for OK button click
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

        self.approval_status_options = [
            "-",
            "approved",
            "not approved",
            "conditionally approved",
        ]

        grid = Windows.Controls.Grid()
        grid.ColumnDefinitions.Add(
            Windows.Controls.ColumnDefinition(
                Width=Windows.GridLength(1, Windows.GridUnitType.Star)
            )
        )
        grid.ColumnDefinitions.Add(
            Windows.Controls.ColumnDefinition(
                Width=Windows.GridLength(1, Windows.GridUnitType.Star)
            )
        )
        grid.ColumnDefinitions.Add(
            Windows.Controls.ColumnDefinition(
                Width=Windows.GridLength(1, Windows.GridUnitType.Star)
            )
        )
        grid.ColumnDefinitions.Add(
            Windows.Controls.ColumnDefinition(
                Width=Windows.GridLength(1, Windows.GridUnitType.Star)
            )
        )

        discipline_textBlock = Windows.Controls.TextBlock(
            Text=opening.get("discipline", "-")
        )
        discipline_textBlock.SetValue(Windows.Controls.Grid.ColumnProperty, 0)

        mark_textBlock = Windows.Controls.TextBlock(Text=opening.get("mark", "-"))
        mark_textBlock.SetValue(Windows.Controls.Grid.ColumnProperty, 1)

        current_approved_textBlock = Windows.Controls.TextBlock(
            Text=opening.get("approved", "-")
        )
        current_approved_textBlock.SetValue(Windows.Controls.Grid.ColumnProperty, 2)

        new_approved_combo = Windows.Controls.ComboBox()
        new_approved_combo.SetValue(Windows.Controls.Grid.ColumnProperty, 3)
        for option in self.approval_status_options:
            combo_item = Windows.Controls.ComboBoxItem()
            combo_item.Content = option
            new_approved_combo.Items.Add(combo_item)
        new_approved_combo.SelectedIndex = 0
        new_approved_combo.SelectionChanged += self.handle_combo_selection_change
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
        if not self.selection_changed_is_on:
            return
        self.combo_selection_changed(self.opening, self.combo_selected_index)

    def get_approved_status(self):
        if self.combo_selected_index < 0 or self.combo_selected_index >= len(
            self.approval_status_options
        ):
            raise ValueError("Invalid combo selection index")
        return self.approval_status_options[self.combo_selected_index]
