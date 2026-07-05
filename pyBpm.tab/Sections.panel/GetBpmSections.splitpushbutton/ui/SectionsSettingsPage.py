# -*- coding: utf-8 -*-
""" In-window Settings page for Get Bpm Sections (R4, decision D4).

The discipline-filter selection - previously the modal FilterSelectionDialog -
reworked as a Windows.Controls.Page hosted in the results window's Frame. Same
grouped-by-discipline Expander layout with per-group and global select/clear and
a 'must pick >= 1' guard.

On save it: persists the selection (SectionsFilterSelection.save_selection),
updates the window's filters + filter_ids (the D6 cache key, so a changed
selection resets the cache on the next read), drops the in-memory computed sheet
pages so they recompute, and enables the sheet nav buttons (D9). Navigating away
without saving discards the edits (the checkboxes re-sync to the saved selection
on each visit via sync_to_current).

IronPython 2.7 / WPF; Hebrew only inside string bodies. """

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from pyrevit.framework import wpf
from pyrevit import forms
import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
import SectionsFilterSelection as sfs  # type: ignore
from RevitUtils import getElementIdValue, getElementName

xaml_file = os.path.join(os.path.dirname(__file__), "SectionsSettingsPage.xaml")


class SectionsSettingsPage(Windows.Controls.Page):
    def __init__(self, res_window):
        wpf.LoadComponent(self, xaml_file)
        self.res_window = res_window
        self.all_pairs = []  # list of (checkbox, ParameterFilterElement)
        self._build_groups()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def _current_selected_ids(self):
        """Filter ids of the window's current saved selection (empty if none)."""
        ids = set()
        comp_doc = self.res_window.comp_doc
        for f in (self.res_window.filters or []):
            ids.add(getElementIdValue(comp_doc, f.Id))
        return ids

    def _build_groups(self):
        try:
            comp_doc = self.res_window.comp_doc
            groups = sfs.collect_discipline_filters(comp_doc)
            self.groups_panel.Children.Clear()
            self.all_pairs = []

            if not groups:
                text_block = Windows.Controls.TextBlock()
                text_block.Text = sfs.NO_FILTERS_MSG
                text_block.TextWrapping = Windows.TextWrapping.Wrap
                self.groups_panel.Children.Add(text_block)
                return

            preselected_ids = self._current_selected_ids()
            for group in groups:
                expander = Windows.Controls.Expander()
                expander.IsExpanded = True
                expander.Margin = Windows.Thickness(0, 0, 0, 6)
                expander.Header = u"{} ({})".format(
                    group["display"], len(group["filters"])
                )

                content = Windows.Controls.StackPanel()
                group_checkboxes = []

                btn_row = Windows.Controls.StackPanel()
                btn_row.Orientation = Windows.Controls.Orientation.Horizontal
                btn_row.Margin = Windows.Thickness(0, 0, 0, 4)

                select_group_btn = Windows.Controls.Button()
                select_group_btn.Content = u"סמן קבוצה"
                select_group_btn.Margin = Windows.Thickness(0, 0, 4, 0)
                select_group_btn.Padding = Windows.Thickness(6, 1, 6, 1)
                select_group_btn.Click += self._make_group_handler(
                    group_checkboxes, True
                )

                clear_group_btn = Windows.Controls.Button()
                clear_group_btn.Content = u"נקה קבוצה"
                clear_group_btn.Padding = Windows.Thickness(6, 1, 6, 1)
                clear_group_btn.Click += self._make_group_handler(
                    group_checkboxes, False
                )

                btn_row.Children.Add(select_group_btn)
                btn_row.Children.Add(clear_group_btn)
                content.Children.Add(btn_row)

                for f in group["filters"]:
                    checkbox = Windows.Controls.CheckBox()
                    checkbox.Content = getElementName(f)
                    checkbox.Margin = Windows.Thickness(0, 2, 0, 2)
                    fid = getElementIdValue(comp_doc, f.Id)
                    checkbox.IsChecked = fid in preselected_ids
                    content.Children.Add(checkbox)
                    group_checkboxes.append(checkbox)
                    self.all_pairs.append((checkbox, f))

                expander.Content = content
                self.groups_panel.Children.Add(expander)
        except Exception:
            self.res_window.report_error(u"טעינת ההגדרות")

    def _make_group_handler(self, checkboxes, check):
        def handler(sender, e):
            try:
                for checkbox in checkboxes:
                    checkbox.IsChecked = check
            except Exception:
                self.res_window.report_error(u"בחירת קבוצה")

        return handler

    def sync_to_current(self):
        """Re-check the boxes to match the window's saved selection - called each
        time the page is shown so unsaved edits from a prior visit are discarded."""
        try:
            preselected_ids = self._current_selected_ids()
            comp_doc = self.res_window.comp_doc
            for checkbox, f in self.all_pairs:
                checkbox.IsChecked = getElementIdValue(comp_doc, f.Id) in preselected_ids
        except Exception:
            self.res_window.report_error(u"רענון ההגדרות")

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def select_all_click(self, sender, e):
        try:
            for checkbox, f in self.all_pairs:
                checkbox.IsChecked = True
        except Exception:
            self.res_window.report_error(u"סימון הכל")

    def clear_all_click(self, sender, e):
        try:
            for checkbox, f in self.all_pairs:
                checkbox.IsChecked = False
        except Exception:
            self.res_window.report_error(u"ניקוי הכל")

    def save_click(self, sender, e):
        try:
            selected = [f for checkbox, f in self.all_pairs if checkbox.IsChecked]
            if not selected:
                self.res_window.notify(u"יש לבחור לפחות פילטר אחד.")
                return
            self.res_window.apply_filter_selection(selected)
            self.res_window.notify(
                u"נשמרה בחירה של {} פילטרים. הגיליונות פתוחים לחישוב.".format(
                    len(selected)
                )
            )
        except Exception:
            self.res_window.report_error(u"שמירת ההגדרות")
