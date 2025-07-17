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
                revision_tree_view_item.Header = (
                    revision_data.get("name", "-- No Revision Name --")
                    + ", "
                    + revision_data.get("date", "-- No Date --")
                )
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
        self.opening_listbox.Visibility = Windows.Visibility.Visible
        self.titleTextBlock.Text = "ערוך סטטוס אישורים"
        self.explainTextBlock.Text = "ניתן לבחור מספר שורות ביחד עם לחיצה על Ctrl או Shift, ולערוך את הסטטוס של כל הפתחים שנבחרו."

        self.opening_listbox.Items.Clear()
        for opening in openings:
            item = ListBoxItem(opening)
            self.opening_listbox.Items.Add(item)

    def ok_btn_click(self, sender, e):
        # Logic for OK button click
        self.Close()

    def cancel_btn_click(self, sender, e):
        # Logic for Cancel button click
        self.Close()


class ListBoxItem(Windows.Controls.ListBoxItem):
    def __init__(self, opening):
        super(ListBoxItem, self).__init__()
        self.opening = opening

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

        discipline_text = Windows.Controls.TextBlock(
            Text=opening.get("discipline", "-")
        )
        discipline_text.SetValue(Windows.Controls.Grid.ColumnProperty, 0)
        mark_text = Windows.Controls.TextBlock(Text=opening.get("mark", "-"))
        mark_text.SetValue(Windows.Controls.Grid.ColumnProperty, 1)
        current_approved_text = Windows.Controls.TextBlock(
            Text=opening.get("approved", "-")
        )
        current_approved_text.SetValue(Windows.Controls.Grid.ColumnProperty, 2)
        new_approved_combo = Windows.Controls.ComboBox()
        new_approved_combo.SetValue(Windows.Controls.Grid.ColumnProperty, 3)
        
        grid.Children.Add(discipline_text)
        grid.Children.Add(mark_text)
        grid.Children.Add(current_approved_text)
        grid.Children.Add(new_approved_combo)
        
        self.Content = grid
