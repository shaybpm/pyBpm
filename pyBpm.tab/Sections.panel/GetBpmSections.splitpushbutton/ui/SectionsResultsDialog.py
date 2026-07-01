# -*- coding: utf-8 -*-
""" Modeless results window for Get Bpm Sections (Phase 3).

One row per (non-empty, in-scope) SU section: name, sheet, match-score range
(coloured by tier), reference-system count, and an "exists in my model?" flag.
Sheet-scope multi-select at the top (persisted), plus live search and sort.
Read-only in Phase 3 - the Create / Go-to / Delete actions come in Phase 4 via
the External Event pattern. Follows the OpeningExplorer modeless pattern
(rows built as Grids in a StackPanel; shown with .Show()). IronPython 2.7. """

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
import SectionsScoring as scoring  # type: ignore
import SectionsFilterSelection as sfs  # type: ignore
import SectionsCreate as creator  # type: ignore
from ProgressBar import ProgressBar  # extension-level lib

xaml_file = os.path.join(os.path.dirname(__file__), "SectionsResultsDialog.xaml")

# tier -> light background (R, G, B)
_TIER_COLORS = {
    "green": (200, 230, 201),
    "orange": (255, 224, 178),
    "red": (255, 205, 210),
}

# (display label, sort key)
_SORT_OPTIONS = [
    (u"ציון: נמוך אל גבוה", "score_asc"),
    (u"ציון: גבוה אל נמוך", "score_desc"),
    (u"שם חתך", "name"),
    (u"גיליון", "sheet"),
]

# column star widths: section, sheet, score, systems, exists
_COL_WIDTHS = [5, 2, 2.2, 1.4, 1.6]


class SectionsResultsDialog(Windows.Window):
    def __init__(self, uidoc, comp_link, comp_doc, filters):
        wpf.LoadComponent(self, xaml_file)
        self._loaded = False

        self.uidoc = uidoc
        self.doc = uidoc.Document
        self.comp_link = comp_link
        self.comp_doc = comp_doc
        self.filters = filters

        self.items, self.all_sheets = scoring.get_candidate_sections_with_sheets(
            comp_doc
        )
        self.sheet_by_section_name = {}
        for it in self.items:
            self.sheet_by_section_name[it["section"].Name] = it["sheet"]

        saved = sfs.load_sheet_scope(self.doc, self.comp_doc)
        if saved is None:
            self.selected_sheets = set(self.all_sheets)
        else:
            self.selected_sheets = set(s for s in saved if s in self.all_sheets)
            if not self.selected_sheets:
                self.selected_sheets = set(self.all_sheets)

        self.results = []
        self.skipped = 0
        self.sheet_checkboxes = []

        self._build_sheet_checkboxes()
        self._build_sort_combo()
        self._compute()
        self._render()
        self._loaded = True

    # ------------------------------------------------------------------
    # Scope + sort controls
    # ------------------------------------------------------------------
    def _build_sheet_checkboxes(self):
        self.SheetScopePanel.Children.Clear()
        self.sheet_checkboxes = []
        for sheet in self.all_sheets:
            checkbox = Windows.Controls.CheckBox()
            checkbox.Content = sheet
            checkbox.IsChecked = sheet in self.selected_sheets
            checkbox.Margin = Windows.Thickness(0, 2, 12, 2)
            self.SheetScopePanel.Children.Add(checkbox)
            self.sheet_checkboxes.append((checkbox, sheet))

    def _build_sort_combo(self):
        for label, _key in _SORT_OPTIONS:
            self.SortComboBox.Items.Add(label)
        self.SortComboBox.SelectedIndex = 0  # worst score first (section 5.5)

    def _current_sort_key(self):
        idx = self.SortComboBox.SelectedIndex
        if idx < 0 or idx >= len(_SORT_OPTIONS):
            idx = 0
        return _SORT_OPTIONS[idx][1]

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    def _scoped_sections(self):
        return [
            it["section"]
            for it in self.items
            if it["sheet"] in self.selected_sheets
        ]

    def _compute(self):
        sections = self._scoped_sections()
        holder = {"results": [], "skipped": 0}

        def work(progress_bar):
            progress_bar.pre_set_main_status(u"מחשב ציוני התאמה...")

            def progress_cb(i, total, name):
                percent = int(100.0 * i / total) if total else 0
                progress_bar.update_main_status(
                    percent, "{}/{}".format(i + 1, total)
                )

            results, skipped = scoring.compute_all_scores(
                self.doc,
                self.comp_link,
                self.comp_doc,
                self.filters,
                sections=sections,
                progress_cb=progress_cb,
            )
            holder["results"] = results
            holder["skipped"] = skipped

        ProgressBar.exec_with_progressbar(
            work, title="Get Bpm Sections", cancelable=False
        )

        results = holder["results"]
        host_names = creator.get_host_view_names(self.doc)
        for r in results:
            r["exists"] = (
                creator.target_section_name(r["section_name"]) in host_names
            )
            r["sheet"] = self.sheet_by_section_name.get(r["section_name"])
        self.results = results
        self.skipped = holder["skipped"]

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    def _sorted_filtered(self):
        search = ""
        if self.SearchTextBox.Text:
            search = self.SearchTextBox.Text.strip().lower()
        rows = [
            r
            for r in self.results
            if not search or search in r["section_name"].lower()
        ]
        key = self._current_sort_key()
        if key == "score_asc":
            rows.sort(key=lambda r: r["lower"])
        elif key == "score_desc":
            rows.sort(key=lambda r: r["lower"], reverse=True)
        elif key == "name":
            rows.sort(key=lambda r: r["section_name"])
        elif key == "sheet":
            rows.sort(key=lambda r: ((r["sheet"] or ""), r["lower"]))
        return rows

    def _make_row_grid(self, cells, is_header=False, tier=None):
        grid = Windows.Controls.Grid()
        for width in _COL_WIDTHS:
            col = Windows.Controls.ColumnDefinition()
            col.Width = Windows.GridLength(width, Windows.GridUnitType.Star)
            grid.ColumnDefinitions.Add(col)
        for i, text in enumerate(cells):
            text_block = Windows.Controls.TextBlock()
            text_block.Text = text
            text_block.Margin = Windows.Thickness(6, 3, 6, 3)
            text_block.TextTrimming = Windows.TextTrimming.CharacterEllipsis
            if is_header:
                text_block.FontWeight = Windows.FontWeights.Bold
            Windows.Controls.Grid.SetColumn(text_block, i)
            grid.Children.Add(text_block)
        if tier is not None and tier in _TIER_COLORS:
            r, g, b = _TIER_COLORS[tier]
            grid.Background = Windows.Media.SolidColorBrush(
                Windows.Media.Color.FromRgb(r, g, b)
            )
        return grid

    def _render(self):
        self.ResultsPanel.Children.Clear()
        self.ResultsPanel.Children.Add(
            self._make_row_grid(
                [u"חתך", u"גיליון", u"ציון", u"מערכות", u"קיים"], is_header=True
            )
        )
        rows = self._sorted_filtered()
        for r in rows:
            cells = [
                r["section_name"],
                r["sheet"] if r["sheet"] else u"-",
                scoring.format_score(r),
                str(r["n"]),
                u"✓" if r["exists"] else u"✗",
            ]
            tier = scoring.score_tier(r["lower"])
            self.ResultsPanel.Children.Add(
                self._make_row_grid(cells, tier=tier)
            )

        self.SummaryText.Text = (
            u"מציג {} מתוך {} חתכים שחושבו. {} דולגו (ריקים / ללא גאומטריה)."
        ).format(len(rows), len(self.results), self.skipped)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def search_changed(self, sender, e):
        if not self._loaded:
            return
        self._render()

    def sort_changed(self, sender, e):
        if not self._loaded:
            return
        self._render()

    def recompute_click(self, sender, e):
        if not self._loaded:
            return
        selected = set(
            sheet for checkbox, sheet in self.sheet_checkboxes if checkbox.IsChecked
        )
        if not selected:
            self._alert(u"בחר לפחות גיליון אחד.")
            return
        self.selected_sheets = selected
        sfs.save_sheet_scope(self.doc, self.comp_doc, sorted(selected))
        self._compute()
        self._render()

    def _alert(self, message):
        self.Hide()
        forms.alert(message)
        self.Show()
