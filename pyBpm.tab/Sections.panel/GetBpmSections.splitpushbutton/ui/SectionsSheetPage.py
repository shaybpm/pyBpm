# -*- coding: utf-8 -*-
""" Per-sheet results page for Get Bpm Sections - a real DataGrid (R2).

One instance per sheet, created lazily by SectionsResultsWindow on first
navigation. It scores ONLY this sheet's sections, cache-served (the misses are
computed once through the modal ProgressBar, decision D5), then shows them in a
sortable, per-column-filterable DataGrid coloured by score tier.

Rows are plain IronPython objects (SectionsRowItem); WPF binds directly to their
attributes ({Binding section_name} etc.) - the proven CoordChecker pattern. The
filter machinery (FilterItem / is_row_visible / initialize_data_grid /
Filter_*_Changed / ClearFilters) is ported from CoordChecker's
ResultsPage_GenericClass, adapted to flat attribute paths.

Empty sections (0 reference systems) are shown, not dropped (decision D7): an
'empty' row with n=0, score '-', a neutral-gray tier, hidden via the systems
filter if the planner wants. Per-row + multi-select bulk actions (Create /
Go-to / Delete via the window's External Event, plus a local Recompute) are
wired in R3. IronPython 2.7 / WPF; Hebrew only inside string bodies. """

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from System.ComponentModel import SortDescription, ListSortDirection
from pyrevit.framework import wpf
import os, sys, traceback

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
import SectionsScoring as scoring  # type: ignore
import SectionsCreate as creator  # type: ignore
import SectionsCache as cache  # type: ignore
import RevitUtils  # extension-level lib
from ProgressBar import ProgressBar  # extension-level lib

xaml_file = os.path.join(os.path.dirname(__file__), "SectionsSheetPage.xaml")


class ControlTypes:
    TEXT_BOX = "text_box"
    COMBO_BOX = "combo_box"


class FilterItem:
    def __init__(self, path, value, control_ref, control_type):
        self.path = path
        self.value = value
        self.control_ref = control_ref
        self.control_type = control_type


class SectionsRowItem(object):
    """Bindable row object for one section. Only the attributes read by the XAML
    bindings/filters/sort are meaningful to WPF; `section` and `result` are held
    for later phases (actions, recompute)."""

    def __init__(self, record, section, sheet, host_names):
        self.result = record  # cached score dict (or empty marker)
        self.section = section  # comp View
        self.section_name = record["section_name"]
        self.sheet = sheet if sheet else u"-"
        self.n = int(record.get("n", 0))
        self.has_systems = self.n > 0
        # Numeric sort key: empty sections use -1 so they sort predictably first.
        # MUST be a float for ALL rows - WPF sorts the column with .NET's default
        # comparer, which throws "Failed to compare two elements in the array" if
        # it is asked to compare a System.Int32 (empty rows' -1) against a
        # System.Double (a scored row's float lower). Coercing every value to
        # float keeps the whole column one .NET type.
        self.result_lower = float(record.get("lower", -1))
        if self.has_systems:
            self.score_text = scoring.format_score(record)
            self.tier = scoring.score_tier(self.result_lower)
        else:
            self.score_text = u"—"
            self.tier = "empty"
        self.exists = creator.target_section_name(self.section_name) in host_names
        self.exists_text = u"קיים" if self.exists else u"לא קיים"


class SectionsSheetPage(Windows.Controls.Page):
    def __init__(self, res_window, sheet, sections):
        # Set state BEFORE LoadComponent so a handler firing during component
        # realization (e.g. a header ComboBox SelectionChanged) never sees a
        # half-built page (self.res_window / self.filters must already exist).
        self.res_window = res_window
        self.sheet = sheet
        self.sections = sections  # comp View objects on this sheet
        self.items = []
        self.filters = []  # type: list[FilterItem]
        self.filter_event_is_on = True
        self._computed = False
        self._default_sorted = False
        self._score_cache = None

        wpf.LoadComponent(self, xaml_file)
        self.Title = sheet if sheet else u"-"

    # ------------------------------------------------------------------
    # Lazy compute (decision D5) + cache (decision D6 key set on the window)
    # ------------------------------------------------------------------
    def ensure_computed(self, force_sections=None):
        """Compute this sheet's scores on first navigation (or force a subset).
        Guarded so the heavy pass runs once; R3 resets it for Recompute.

        Fully wrapped: this runs from the modeless window's Click handler, where
        an unhandled exception crashes Revit - so any failure is shown, not
        propagated. Returns True on success, False on a handled failure (the
        window then must NOT navigate to this half-built page - rendering a
        DataGrid left with a poisoned SortDescription re-throws on the render
        path, outside any try/except, and crashes Revit)."""
        try:
            if self._computed and not force_sections:
                return True
            if not self.res_window.has_filters():
                return False  # sheets locked without a selection (D9) - defensive
            self._compute(force_sections)
            self._computed = True
            self._build_items()
            self.initialize_data_grid()
            if not self._default_sorted:
                self._apply_default_sort()
                self._default_sorted = True
            return True
        except Exception:
            # Allow a later retry, and drop any half-applied (poisoned) sort so a
            # subsequent render can't re-throw and crash Revit.
            self._computed = False
            try:
                self.DataGrid.Items.SortDescriptions.Clear()
            except Exception:
                pass
            self.res_window.report_error(u"חישוב גיליון")
            return False

    def _compute(self, force_sections=None):
        win = self.res_window
        score_cache = cache.SectionsScoreCache(
            win.doc, win.comp_doc, win.filter_ids
        )

        forced_ids = set()
        to_compute = []
        if force_sections:
            to_compute = list(force_sections)
            forced_ids = set(
                scoring.section_id_value(win.comp_doc, s) for s in force_sections
            )
        for section in self.sections:
            section_id = scoring.section_id_value(win.comp_doc, section)
            if section_id in forced_ids:
                continue
            if score_cache.get(section_id) is None:
                to_compute.append(section)

        if to_compute:
            self._compute_into_cache(to_compute, score_cache)
        self._score_cache = score_cache

    def _compute_into_cache(self, sections, score_cache):
        """Force-(re)score the given sections into the cache (modal ProgressBar).

        A transient exception is NOT cached (retried next visit). A section with
        no reference systems (score_section -> None) is cached as a displayable
        EMPTY record (decision D7), not hidden."""
        win = self.res_window
        errors = []

        def work(progress_bar):
            progress_bar.pre_set_main_status(u"מחשב ציוני התאמה...")
            total = len(sections)
            for i, section in enumerate(sections):
                percent = int(100.0 * i / total) if total else 0
                progress_bar.update_main_status(
                    percent, "{}/{}".format(i + 1, total)
                )
                try:
                    result = scoring.score_section(
                        win.doc,
                        win.comp_link,
                        win.comp_doc,
                        section,
                        win.filters,
                    )
                except Exception:
                    # Transient failure - leave uncached so it retries next visit
                    # (never poison the cache with a bad score). Recorded so it is
                    # surfaced after the run, not silently swallowed.
                    try:
                        name = RevitUtils.getElementName(section)
                    except Exception:
                        name = "?"
                    errors.append((name, traceback.format_exc()))
                    continue
                if result is None:
                    score_cache.put(self._empty_record(section))
                else:
                    score_cache.put(result)
            score_cache.save()

        ProgressBar.exec_with_progressbar(
            work, title="Get Bpm Sections", cancelable=False
        )

        if errors:
            self._report_section_errors(errors)

    def _report_section_errors(self, errors):
        """A few sections failed to score and were skipped. Print the full
        tracebacks for debugging (pyRevit output), but show the planner only a
        concise, friendly note - a raw Python traceback is not appropriate for a
        client office (this is a customer-facing tool)."""
        for name, trace in errors:
            print(
                u"[GetBpmSections] section '{}' failed to score:\n{}".format(
                    name, trace
                )
            )
        names = u", ".join(name for name, _ in errors[:10])
        more = u" ..." if len(errors) > 10 else u""
        message = u"{} חתכים לא חושבו ודולגו:\n{}{}".format(
            len(errors), names, more
        )
        try:
            self.res_window.notify(message)
        except Exception:
            pass

    def _empty_record(self, section):
        """Displayable record for a section with 0 reference systems (D7). Carries
        all cache result fields so SectionsScoreCache.put stores it normally."""
        return {
            "section_name": RevitUtils.getElementName(section),
            "section_id": scoring.section_id_value(self.res_window.comp_doc, section),
            "lower": -1,
            "upper": -1,
            "n": 0,
            "failed": 0,
            "systems": [],
        }

    def _build_items(self):
        win = self.res_window
        host_names = creator.get_host_view_names(win.doc)
        self.items = []
        for section in self.sections:
            section_id = scoring.section_id_value(win.comp_doc, section)
            record = self._score_cache.get(section_id)
            if record is None:
                continue  # transient failure - not cached, retried next visit
            if record.get("skipped"):
                continue  # legacy pre-D7 marker (normally invalidated by D6)
            self.items.append(
                SectionsRowItem(record, section, self.sheet, host_names)
            )

    def _apply_default_sort(self):
        """Worst-first: sort by the numeric lower-bound ascending (section 5.4)."""
        self.DataGrid.Items.SortDescriptions.Clear()
        self.DataGrid.Items.SortDescriptions.Add(
            SortDescription("result_lower", ListSortDirection.Ascending)
        )
        self.DataGrid.Items.Refresh()

    # ------------------------------------------------------------------
    # DataGrid population + filtering (ported from CoordChecker GenericClass)
    # ------------------------------------------------------------------
    def is_row_visible(self, row):
        if not self.filters:
            return True
        for filter_item in self.filters:
            attr = row
            for path_part in filter_item.path.split("."):
                attr = getattr(attr, path_part, None)
                if attr is None:
                    break
            if attr is None or str(attr).lower().find(filter_item.value.lower()) == -1:
                return False
        return True

    def initialize_data_grid(self):
        sort_descriptions_copy = [
            sort_desc for sort_desc in self.DataGrid.Items.SortDescriptions
        ]
        self.DataGrid.Items.Clear()
        showing = 0
        for row in self.items:
            if not self.is_row_visible(row):
                continue
            showing += 1
            self.DataGrid.Items.Add(row)
        self.DataGrid.Items.SortDescriptions.Clear()
        for sort_desc in sort_descriptions_copy:
            self.DataGrid.Items.SortDescriptions.Add(sort_desc)
        self.set_status_text_block(
            u"סה\"כ: {}, מוצג: {}".format(len(self.items), showing)
        )

    def set_status_text_block(self, text):
        self.StatusTextBlock.Text = text

    def filter_changed_helper(self, control, path, value, control_type):
        for filter_item in self.filters:
            if filter_item.path == path:
                if value:
                    filter_item.value = value
                else:
                    self.filters.remove(filter_item)
                break
        else:
            if value:
                self.filters.append(
                    FilterItem(path, value, control, control_type)
                )
        self.initialize_data_grid()

    def Filter_TextBox_TextChanged(self, sender, e):
        if not self.filter_event_is_on:
            return
        try:
            text_box = sender
            text = text_box.Text.strip()
            self.filter_changed_helper(
                text_box, text_box.Tag, text, ControlTypes.TEXT_BOX
            )
        except Exception:
            self.res_window.report_error(u"סינון")

    def Filter_ComboBox_SelectionChanged(self, sender, e):
        if not self.filter_event_is_on:
            return
        try:
            combo_box = sender
            text = combo_box.SelectedItem.Tag.strip() if combo_box.SelectedItem else ""
            self.filter_changed_helper(
                combo_box, combo_box.Tag, text, ControlTypes.COMBO_BOX
            )
        except Exception:
            self.res_window.report_error(u"סינון")

    def ClearFilters_Click(self, sender, e):
        try:
            self.filter_event_is_on = False
            try:
                for filter_item in self.filters:
                    if filter_item.control_type == ControlTypes.TEXT_BOX:
                        filter_item.control_ref.Text = ""
                    elif filter_item.control_type == ControlTypes.COMBO_BOX:
                        filter_item.control_ref.SelectedIndex = 0
                self.filters = []
                self.initialize_data_grid()
            finally:
                # Always re-arm filtering, even if the rebuild threw - otherwise
                # this page's filters would be silently dead until it is rebuilt.
                self.filter_event_is_on = True
        except Exception:
            self.res_window.report_error(u"ניקוי פילטרים")

    # ------------------------------------------------------------------
    # Selection + row actions (R3). All Revit writes go through the window's
    # External Event; the recompute is a local cache/scoring pass.
    # ------------------------------------------------------------------
    def SelectAll_Click(self, sender, e):
        try:
            self.DataGrid.SelectAll()
        except Exception:
            self.res_window.report_error(u"בחירת הכל")

    def UnselectAll_Click(self, sender, e):
        try:
            self.DataGrid.UnselectAll()
        except Exception:
            self.res_window.report_error(u"ניקוי בחירה")

    def get_selected_rows(self):
        """The SectionsRowItem objects currently selected in the grid."""
        return [row for row in self.DataGrid.SelectedItems]

    def _rows_for_action(self, clicked_row):
        """Bulk rule (D3): act on the whole selection if the clicked row is part
        of it, otherwise just the clicked row (CoordChecker is_row_in_rows)."""
        selected = self.get_selected_rows()
        for row in selected:
            if row is clicked_row:
                return selected
        return [clicked_row]

    def Create_Click(self, sender, e):
        try:
            self.res_window.request_action(
                "create", self._rows_for_action(sender.DataContext)
            )
        except Exception:
            self.res_window.report_error(u"יצירת חתך")

    def GoTo_Click(self, sender, e):
        try:
            self.res_window.request_action(
                "goto", self._rows_for_action(sender.DataContext)
            )
        except Exception:
            self.res_window.report_error(u"מעבר לחתך")

    def Delete_Click(self, sender, e):
        try:
            self.res_window.request_action(
                "delete", self._rows_for_action(sender.DataContext)
            )
        except Exception:
            self.res_window.report_error(u"מחיקת חתך")

    def Recompute_Click(self, sender, e):
        try:
            # Recompute is a bulk action too (D3): act on the whole selection when
            # the clicked row is part of it, else just the clicked row.
            rows = self._rows_for_action(sender.DataContext)
            self.recompute([row.section for row in rows])
        except Exception:
            self.res_window.report_error(u"חישוב חתך מחדש")

    def RecomputeSheet_Click(self, sender, e):
        try:
            self.recompute(self.sections)
        except Exception:
            self.res_window.report_error(u"חישוב גיליון מחדש")

    def recompute(self, sections):
        """Force-(re)score the given sections into the cache and rebuild the grid,
        preserving the current sort + filters (initialize_data_grid keeps them)."""
        if not sections:
            return
        if not self.res_window.has_filters():
            return
        self._compute(sections)
        self._build_items()
        self.initialize_data_grid()

    def refresh_exists(self):
        """Re-derive every row's exists flag from the live model after a Create /
        Delete, then refresh the grid so the action buttons (bound to `exists`)
        swap. Called by the window after the External Event runs."""
        try:
            host_names = creator.get_host_view_names(self.res_window.doc)
            for row in self.items:
                row.exists = (
                    creator.target_section_name(row.section_name) in host_names
                )
                row.exists_text = u"קיים" if row.exists else u"לא קיים"
            # Rebuild rather than a bare Items.Refresh(): a row whose exists just
            # flipped must be re-tested against an active "קיים/לא קיים" filter,
            # and the exists-bound action buttons re-evaluated. initialize_data_grid
            # re-applies filters + keeps the sort.
            self.initialize_data_grid()
        except Exception:
            self.res_window.report_error(u"רענון מצב חתכים")
