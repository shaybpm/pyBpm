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
from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent
from Autodesk.Revit.DB import Transaction
import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
import SectionsScoring as scoring  # type: ignore
import SectionsFilterSelection as sfs  # type: ignore
import SectionsCreate as creator  # type: ignore
import SectionsCache as cache  # type: ignore
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

# column star widths: section, sheet, score, systems, actions
_COL_WIDTHS = [5, 2, 2.2, 1.4, 2.2]


class SectionActionEventHandler(IExternalEventHandler):
    """Runs the pending Create / Delete / Go-to on Revit's API context (same
    thread as the window), then lets the window refresh the affected row."""

    def __init__(self, window):
        self.window = window

    def Execute(self, uiapp):
        try:
            self.window.execute_pending_action(uiapp)
        except Exception as ex:
            print(ex)

    def GetName(self):
        return "BPM Get Bpm Sections Action"


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
        self.section_by_name = {}
        for it in self.items:
            self.sheet_by_section_name[it["section"].Name] = it["sheet"]
            self.section_by_name[it["section"].Name] = it["section"]

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

        # External Event: all Revit writes (create/delete/goto) run through it.
        # _pending is a QUEUE - Revit coalesces rapid Raise() calls into a single
        # Execute, so a shared single slot would silently drop earlier actions.
        self._pending = []
        self._action_handler = SectionActionEventHandler(self)
        self._action_event = ExternalEvent.Create(self._action_handler)

        self._build_sheet_checkboxes()
        self._build_sort_combo()
        self._load_display()
        self._render()
        self._loaded = True

    # ------------------------------------------------------------------
    # Scope + sort controls
    # ------------------------------------------------------------------
    def _build_sheet_checkboxes(self):
        self.SheetScopePanel.Children.Clear()
        self.sheet_checkboxes = []
        for sheet in self.all_sheets:
            entry = Windows.Controls.StackPanel()
            entry.Orientation = Windows.Controls.Orientation.Horizontal
            entry.Margin = Windows.Thickness(0, 2, 14, 2)

            checkbox = Windows.Controls.CheckBox()
            checkbox.Content = sheet
            checkbox.IsChecked = sheet in self.selected_sheets
            checkbox.VerticalAlignment = Windows.VerticalAlignment.Center
            entry.Children.Add(checkbox)

            recompute_button = Windows.Controls.Button()
            recompute_button.Content = u"↻"
            recompute_button.ToolTip = u"חשב את גיליון זה מחדש"
            recompute_button.Margin = Windows.Thickness(4, 0, 0, 0)
            recompute_button.Padding = Windows.Thickness(4, 0, 4, 0)
            recompute_button.Click += self._make_recompute_sheet_handler(sheet)
            entry.Children.Add(recompute_button)

            self.SheetScopePanel.Children.Add(entry)
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

    def _compute_into_cache(self, sections, score_cache):
        """Force-(re)score the given sections and write them into the cache."""

        def work(progress_bar):
            progress_bar.pre_set_main_status(u"מחשב ציוני התאמה...")
            total = len(sections)
            for i, section in enumerate(sections):
                percent = int(100.0 * i / total) if total else 0
                progress_bar.update_main_status(
                    percent, "{}/{}".format(i + 1, total)
                )
                try:
                    section_id = scoring.section_id_value(self.comp_doc, section)
                    result = scoring.score_section(
                        self.doc,
                        self.comp_link,
                        self.comp_doc,
                        section,
                        self.filters,
                    )
                except Exception as ex:
                    # A transient failure must NOT be cached as a skipped marker
                    # (that would permanently hide a section that has a real score,
                    # or overwrite a good cached score on a forced recompute).
                    # Leaving it uncached means it is retried on the next load.
                    print(ex)
                    continue
                if result is None:
                    score_cache.put_skipped(section_id)  # genuinely empty section
                else:
                    score_cache.put(result)
            score_cache.save()

        ProgressBar.exec_with_progressbar(
            work, title="Get Bpm Sections", cancelable=False
        )

    def _load_display(self, force_sections=None):
        """Build self.results for the in-scope sections from the cache. Cache
        misses (and the force_sections subset - used by the Recompute buttons)
        are (re)computed and cached; the rest are served from the local file
        (valid while the comp version + daily stamp match, see SectionsCache)."""
        score_cache = cache.SectionsScoreCache(self.doc, self.comp_doc)
        scoped = self._scoped_sections()

        forced_ids = set()
        to_compute = []
        if force_sections:
            to_compute = list(force_sections)
            forced_ids = set(
                scoring.section_id_value(self.comp_doc, s) for s in force_sections
            )
        for section in scoped:
            section_id = scoring.section_id_value(self.comp_doc, section)
            if section_id in forced_ids:
                continue
            if score_cache.get(section_id) is None:
                to_compute.append(section)

        if to_compute:
            self._compute_into_cache(to_compute, score_cache)

        results = []
        skipped = 0
        for section in scoped:
            record = score_cache.get(
                scoring.section_id_value(self.comp_doc, section)
            )
            if record is None or record.get("skipped"):
                skipped += 1
            else:
                results.append(dict(record))

        host_names = creator.get_host_view_names(self.doc)
        for r in results:
            r["exists"] = (
                creator.target_section_name(r["section_name"]) in host_names
            )
            r["sheet"] = self.sheet_by_section_name.get(r["section_name"])
        self.results = results
        self.skipped = skipped

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

    def _make_data_row(self, r):
        grid = Windows.Controls.Grid()
        for width in _COL_WIDTHS:
            col = Windows.Controls.ColumnDefinition()
            col.Width = Windows.GridLength(width, Windows.GridUnitType.Star)
            grid.ColumnDefinitions.Add(col)

        texts = [
            r["section_name"],
            r["sheet"] if r["sheet"] else u"-",
            scoring.format_score(r),
            str(r["n"]),
        ]
        for i, text in enumerate(texts):
            text_block = Windows.Controls.TextBlock()
            text_block.Text = text
            text_block.Margin = Windows.Thickness(6, 3, 6, 3)
            text_block.VerticalAlignment = Windows.VerticalAlignment.Center
            text_block.TextTrimming = Windows.TextTrimming.CharacterEllipsis
            Windows.Controls.Grid.SetColumn(text_block, i)
            grid.Children.Add(text_block)

        actions = Windows.Controls.StackPanel()
        actions.Orientation = Windows.Controls.Orientation.Horizontal
        Windows.Controls.Grid.SetColumn(actions, 4)
        if r["exists"]:
            actions.Children.Add(self._action_button(u"מעבר", r, "goto"))
            actions.Children.Add(self._action_button(u"מחיקה", r, "delete"))
        else:
            actions.Children.Add(self._action_button(u"יצירה", r, "create"))
        recompute_button = Windows.Controls.Button()
        recompute_button.Content = u"↻"
        recompute_button.ToolTip = u"חשב חתך זה מחדש"
        recompute_button.Margin = Windows.Thickness(0, 1, 4, 1)
        recompute_button.Padding = Windows.Thickness(6, 1, 6, 1)
        recompute_button.Click += self._make_recompute_section_handler(
            r["section_name"]
        )
        actions.Children.Add(recompute_button)
        grid.Children.Add(actions)

        tier = scoring.score_tier(r["lower"])
        if tier in _TIER_COLORS:
            red, green, blue = _TIER_COLORS[tier]
            grid.Background = Windows.Media.SolidColorBrush(
                Windows.Media.Color.FromRgb(red, green, blue)
            )
        return grid

    def _action_button(self, label, row, action):
        button = Windows.Controls.Button()
        button.Content = label
        button.Margin = Windows.Thickness(0, 1, 4, 1)
        button.Padding = Windows.Thickness(6, 1, 6, 1)
        button.Click += self._make_action_handler(row, action)
        return button

    def _render(self):
        self.ResultsPanel.Children.Clear()
        self.ResultsPanel.Children.Add(
            self._make_row_grid(
                [u"חתך", u"גיליון", u"ציון", u"מערכות", u"פעולות"], is_header=True
            )
        )
        rows = self._sorted_filtered()
        for r in rows:
            self.ResultsPanel.Children.Add(self._make_data_row(r))

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
        self._load_display()
        self._render()

    def recompute_all_click(self, sender, e):
        if not self._loaded:
            return
        self._load_display(force_sections=self._scoped_sections())
        self._render()

    def _recompute_section(self, name):
        section = self.section_by_name.get(name)
        if section is None:
            return
        self._load_display(force_sections=[section])
        self._render()

    def _recompute_sheet(self, sheet):
        sections = [
            it["section"]
            for it in self.items
            if it["sheet"] == sheet and it["sheet"] in self.selected_sheets
        ]
        if not sections:
            return
        self._load_display(force_sections=sections)
        self._render()

    def _make_recompute_section_handler(self, name):
        def handler(sender, e):
            if self._loaded:
                self._recompute_section(name)

        return handler

    def _make_recompute_sheet_handler(self, sheet):
        def handler(sender, e):
            if self._loaded:
                self._recompute_sheet(sheet)

        return handler

    def _alert(self, message):
        self.Hide()
        forms.alert(message)
        self.Show()

    def _confirm(self, message):
        self.Hide()
        result = forms.alert(message, yes=True, no=True)
        self.Show()
        return result

    # ------------------------------------------------------------------
    # Actions (all Revit writes go through the External Event)
    # ------------------------------------------------------------------
    def _make_action_handler(self, row, action):
        def handler(sender, e):
            self._do_action(row, action)

        return handler

    def _do_action(self, row, action):
        if not self._loaded:
            return
        name = row["section_name"]  # carry the name, not the (possibly stale) dict
        if action == "create":
            type_id = creator.get_type_id(self.doc)  # may prompt (UI thread)
            if not type_id:
                return
            self._pending.append(
                {"action": "create", "name": name, "type_id": type_id}
            )
        elif action == "delete":
            target = creator.target_section_name(name)
            if not self._confirm(u"למחוק את החתך '{}'?".format(target)):
                return
            self._pending.append({"action": "delete", "name": name})
        elif action == "goto":
            self._pending.append({"action": "goto", "name": name})
        else:
            return
        self._action_event.Raise()

    def execute_pending_action(self, uiapp):
        """Runs on Revit's API context (via the External Event). Drains the whole
        queue, since Revit coalesces rapid Raise() calls into a single Execute."""
        requests = self._pending
        self._pending = []
        changed = False
        for request in requests:
            try:
                if self._run_action(uiapp, request):
                    changed = True
            except Exception as ex:
                print(ex)
        if changed:
            self._refresh_exists()

    def _run_action(self, uiapp, request):
        """Perform one action. Returns True if an exists-state may have changed."""
        action = request["action"]
        name = request["name"]

        if action == "create":
            # Never create a second, suffixed copy: Create is only valid while the
            # exact name is free. Re-check here in case a stale/duplicate click got
            # through (section 4.5).
            if creator.find_existing_section(self.doc, name) is not None:
                return True
            comp_section = self.section_by_name.get(name)
            if comp_section is None:
                return False
            transform = self.comp_link.GetTotalTransform()
            t = Transaction(self.doc, "pyBpm | Create Bpm Section")
            t.Start()
            new_view = None
            try:
                new_view = creator.create_section(
                    self.doc, comp_section, request["type_id"], transform
                )
            except Exception as ex:
                print(ex)
            if new_view is not None:
                t.Commit()
                return True
            t.RollBack()
            return False

        if action == "delete":
            view = creator.find_existing_section(self.doc, name)
            if view is not None:
                t = Transaction(self.doc, "pyBpm | Delete Bpm Section")
                t.Start()
                try:
                    self.doc.Delete(view.Id)
                    t.Commit()
                except Exception as ex:
                    print(ex)
                    t.RollBack()
            return True

        if action == "goto":
            view = creator.find_existing_section(self.doc, name)
            if view is not None:
                uiapp.ActiveUIDocument.ActiveView = view
            return False

        return False

    def _refresh_exists(self):
        """Re-derive every displayed row's exists flag from the live model, then
        re-render - robust against stale row dicts and recompute races."""
        host_names = creator.get_host_view_names(self.doc)
        for r in self.results:
            r["exists"] = (
                creator.target_section_name(r["section_name"]) in host_names
            )
        self._render()
