# -*- coding: utf-8 -*-
""" In-window Settings page for Get Bpm Sections (R4, decision D4).

A shell page with its own sub-navigation (מסננים / יצירת חתך) hosted in the
results window's Frame. The two sub-pages are stacked panels toggled by
Visibility (the same code-driven toggle pattern used elsewhere in this window),
which sidesteps the nested-Frame resource isolation problem.

Filters sub-page: the discipline-filter selection - previously the modal
FilterSelectionDialog - as a grouped-by-discipline Expander list. Groups are
COLLAPSED by default; each group's header carries a tri-state indicator (all /
partial / none selected) plus per-group select/clear buttons, so both stay
visible while the group is collapsed. Global select/clear + a 'must pick >= 1'
guard on save.

On save it: persists the selection (SectionsFilterSelection.save_selection),
updates the window's filters + filter_ids (the D6 cache key, so a changed
selection resets the cache on the next read), drops the in-memory computed sheet
pages so they recompute, and enables the sheet nav buttons (D9). Navigating away
without saving discards the edits (the checkboxes re-sync to the saved selection
on each visit via sync_to_current).

Section-creation sub-page: a placeholder for now - options are added later.

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
import SectionsCreate as creator  # type: ignore
from RevitUtils import getElementIdValue, getElementName

xaml_file = os.path.join(os.path.dirname(__file__), "SectionsSettingsPage.xaml")


class SectionsSettingsPage(Windows.Controls.Page):
    def __init__(self, res_window):
        wpf.LoadComponent(self, xaml_file)
        self.res_window = res_window
        self.all_pairs = []  # list of (checkbox, ParameterFilterElement)
        # Per-group tri-state indicator state: list of (indicator_checkbox,
        # [child_checkboxes]) - drives the all/partial/none header indicator.
        self.group_states = []
        # While a bulk change is in progress the per-child toggle handler skips
        # the indicator refresh (done once at the end) to avoid O(n) churn.
        self._suspend_indicator = False
        # Same guard for the create-option combos (populate/sync fire
        # SelectionChanged, which must not be read as a user edit).
        self._suspend_create = False
        self.active_nav_bg = Windows.Media.Brushes.LightBlue
        # Create options first: _build_groups ends with _update_save_enabled,
        # which reads the create combos, so they must already be populated.
        self._build_create_options()
        self._build_groups()
        self.show_filters()  # default sub-page

    # ------------------------------------------------------------------
    # Sub-navigation (מסננים / יצירת חתך)
    # ------------------------------------------------------------------
    def _activate_subnav(self, active):
        """Highlight the active sub-nav button (LightBlue, like the main nav) and
        clear the other back to its style default."""
        try:
            bg_prop = Windows.Controls.Control.BackgroundProperty
            if active == "filters":
                self.FiltersNavButton.Background = self.active_nav_bg
                self.CreateNavButton.ClearValue(bg_prop)
            else:
                self.CreateNavButton.Background = self.active_nav_bg
                self.FiltersNavButton.ClearValue(bg_prop)
        except Exception:
            pass

    def show_filters(self):
        self.FiltersPanel.Visibility = Windows.Visibility.Visible
        self.CreatePanel.Visibility = Windows.Visibility.Collapsed
        self._activate_subnav("filters")

    def show_create(self):
        self.FiltersPanel.Visibility = Windows.Visibility.Collapsed
        self.CreatePanel.Visibility = Windows.Visibility.Visible
        self._activate_subnav("create")

    def show_filters_click(self, sender, e):
        try:
            self.show_filters()
        except Exception:
            self.res_window.report_error(u"מעבר לדף המסננים")

    def show_create_click(self, sender, e):
        try:
            self.show_create()
        except Exception:
            self.res_window.report_error(u"מעבר לדף יצירת חתך")

    # ------------------------------------------------------------------
    # Create options sub-page (Section Type / View Template)
    # ------------------------------------------------------------------
    def _add_combo_item(self, combo, label, id_value):
        item = Windows.Controls.ComboBoxItem()
        item.Content = label
        item.Tag = id_value  # None (default / none) or an element-id int
        combo.Items.Add(item)

    def _build_create_options(self):
        """Populate the Section Type + View Template combos from the host doc and
        select the saved values. Wrapped in the suspend guard so the initial
        selection does not register as a user edit."""
        try:
            doc = self.res_window.doc
            self._suspend_create = True
            try:
                self.SectionTypeCombo.Items.Clear()
                self._add_combo_item(
                    self.SectionTypeCombo, u"ברירת מחדל של המודל", None
                )
                for vft in creator.get_all_section_viewFamilyTypes(doc):
                    self._add_combo_item(
                        self.SectionTypeCombo,
                        getElementName(vft),
                        getElementIdValue(doc, vft.Id),
                    )

                self.ViewTemplateCombo.Items.Clear()
                self._add_combo_item(self.ViewTemplateCombo, u"ללא", None)
                for vt in creator.get_section_view_templates(doc):
                    self._add_combo_item(
                        self.ViewTemplateCombo,
                        getElementName(vt),
                        getElementIdValue(doc, vt.Id),
                    )

                self.SectionTypeCombo.SelectionChanged += self._on_create_change
                self.ViewTemplateCombo.SelectionChanged += self._on_create_change
                self._select_saved_create()
            finally:
                self._suspend_create = False
        except Exception:
            self.res_window.report_error(u"טעינת הגדרות היצירה")

    def _select_combo(self, combo, id_value):
        for item in combo.Items:
            if item.Tag == id_value:
                combo.SelectedItem = item
                return
        if combo.Items.Count > 0:
            combo.SelectedIndex = 0  # fall back to the default / none row

    def _select_saved_create(self):
        saved = self._saved_create_settings()
        self._select_combo(self.SectionTypeCombo, saved["section_type_id"])
        self._select_combo(self.ViewTemplateCombo, saved["view_template_id"])

    def _combo_value(self, combo):
        item = combo.SelectedItem
        return item.Tag if item is not None else None

    def _current_create_settings(self):
        return {
            "section_type_id": self._combo_value(self.SectionTypeCombo),
            "view_template_id": self._combo_value(self.ViewTemplateCombo),
        }

    def _saved_create_settings(self):
        """The window's persisted create settings, normalized to the two keys."""
        saved = self.res_window.create_settings or {}
        return {
            "section_type_id": saved.get("section_type_id"),
            "view_template_id": saved.get("view_template_id"),
        }

    def _on_create_change(self, sender, e):
        if self._suspend_create:
            return
        try:
            self._update_save_enabled()
        except Exception:
            pass

    def _sync_create_to_saved(self):
        """Re-select the combos to the saved values (discards unsaved edits)."""
        self._suspend_create = True
        try:
            self._select_saved_create()
        finally:
            self._suspend_create = False

    # ------------------------------------------------------------------
    # Build (filters sub-page)
    # ------------------------------------------------------------------
    def _current_selected_ids(self):
        """Filter ids of the window's current saved selection (empty if none)."""
        ids = set()
        comp_doc = self.res_window.comp_doc
        for f in (self.res_window.filters or []):
            ids.add(getElementIdValue(comp_doc, f.Id))
        return ids

    def _styled_button(self, label, key):
        btn = Windows.Controls.Button()
        btn.Content = label
        try:
            btn.Style = self.FindResource(key)
        except Exception:
            pass
        return btn

    def _build_groups(self):
        try:
            comp_doc = self.res_window.comp_doc
            groups = sfs.collect_discipline_filters(comp_doc)
            self.groups_panel.Children.Clear()
            self.all_pairs = []
            self.group_states = []

            if not groups:
                text_block = Windows.Controls.TextBlock()
                text_block.Text = sfs.NO_FILTERS_MSG
                text_block.TextWrapping = Windows.TextWrapping.Wrap
                self.groups_panel.Children.Add(text_block)
                return

            preselected_ids = self._current_selected_ids()
            for group in groups:
                expander = Windows.Controls.Expander()
                expander.IsExpanded = False  # collapsed by default
                expander.Margin = Windows.Thickness(0, 0, 0, 6)

                group_checkboxes = []

                # Tri-state indicator (all / partial / none). Non-interactive - it
                # only reflects state; the buttons do the selecting.
                indicator = Windows.Controls.CheckBox()
                indicator.IsThreeState = True
                indicator.IsHitTestVisible = False
                indicator.Focusable = False
                indicator.VerticalAlignment = Windows.VerticalAlignment.Center
                indicator.Margin = Windows.Thickness(0, 0, 6, 0)

                # Header: [indicator] [name (count)]  [select] [clear]. Buttons in
                # the header stay visible while the group is collapsed.
                header = Windows.Controls.StackPanel()
                header.Orientation = Windows.Controls.Orientation.Horizontal

                label = Windows.Controls.TextBlock()
                label.Text = u"{} ({})".format(
                    group["display"], len(group["filters"])
                )
                label.VerticalAlignment = Windows.VerticalAlignment.Center
                label.Margin = Windows.Thickness(0, 0, 10, 0)

                select_group_btn = self._styled_button(u"סמן", "SmallButton")
                select_group_btn.Click += self._make_group_handler(
                    group_checkboxes, True
                )
                clear_group_btn = self._styled_button(u"נקה", "SmallButton")
                clear_group_btn.Click += self._make_group_handler(
                    group_checkboxes, False
                )

                header.Children.Add(indicator)
                header.Children.Add(label)
                header.Children.Add(select_group_btn)
                header.Children.Add(clear_group_btn)
                expander.Header = header

                content = Windows.Controls.StackPanel()
                content.Margin = Windows.Thickness(18, 2, 0, 2)
                for f in group["filters"]:
                    checkbox = Windows.Controls.CheckBox()
                    checkbox.Content = getElementName(f)
                    checkbox.Margin = Windows.Thickness(0, 2, 0, 2)
                    fid = getElementIdValue(comp_doc, f.Id)
                    checkbox.IsChecked = fid in preselected_ids
                    checkbox.Checked += self._on_child_toggle
                    checkbox.Unchecked += self._on_child_toggle
                    content.Children.Add(checkbox)
                    group_checkboxes.append(checkbox)
                    self.all_pairs.append((checkbox, f))

                expander.Content = content
                self.groups_panel.Children.Add(expander)
                self.group_states.append((indicator, group_checkboxes))

            self._refresh_indicators()
            self._update_save_enabled()
        except Exception:
            self.res_window.report_error(u"טעינת ההגדרות")

    # ------------------------------------------------------------------
    # Tri-state indicators
    # ------------------------------------------------------------------
    def _refresh_indicators(self):
        """Set each group's header indicator to all (True) / none (False) /
        partial (None = indeterminate) from its child checkboxes."""
        for indicator, children in self.group_states:
            total = len(children)
            checked = 0
            for c in children:
                if c.IsChecked:
                    checked += 1
            if total == 0 or checked == 0:
                indicator.IsChecked = False
            elif checked == total:
                indicator.IsChecked = True
            else:
                indicator.IsChecked = None  # indeterminate = partial

    def _on_child_toggle(self, sender, e):
        if self._suspend_indicator:
            return
        try:
            self._refresh_indicators()
            self._update_save_enabled()
        except Exception:
            pass

    def _bulk_set(self, checkboxes, value):
        """Set a batch of checkboxes without per-item indicator churn, then
        refresh the indicators + save-enabled once."""
        self._suspend_indicator = True
        try:
            for checkbox in checkboxes:
                checkbox.IsChecked = value
        finally:
            self._suspend_indicator = False
        self._refresh_indicators()
        self._update_save_enabled()

    # ------------------------------------------------------------------
    # Dirty tracking - the save button is enabled only when the current
    # selection differs from the saved one, and leaving Settings while dirty
    # prompts a confirmation (handled by the window).
    # ------------------------------------------------------------------
    def _current_checked_ids(self):
        comp_doc = self.res_window.comp_doc
        return set(
            getElementIdValue(comp_doc, f.Id)
            for checkbox, f in self.all_pairs
            if checkbox.IsChecked
        )

    def _filters_dirty(self):
        return self._current_checked_ids() != self._current_selected_ids()

    def _create_dirty(self):
        return self._current_create_settings() != self._saved_create_settings()

    def has_unsaved_changes(self):
        """True when the filters selection OR the create settings differ from the
        saved state (the single 'שמור הגדרות' button covers both sub-pages)."""
        try:
            return self._filters_dirty() or self._create_dirty()
        except Exception:
            return False

    def _update_save_enabled(self):
        try:
            self.SaveButton.IsEnabled = self.has_unsaved_changes()
        except Exception:
            pass

    def _make_group_handler(self, checkboxes, check):
        def handler(sender, e):
            try:
                self._bulk_set(checkboxes, check)
            except Exception:
                self.res_window.report_error(u"בחירת קבוצה")

        return handler

    def sync_to_current(self):
        """Re-check the boxes to match the window's saved selection - called each
        time the page is shown so unsaved edits from a prior visit are discarded.
        Also resets the view to the filters sub-page."""
        try:
            preselected_ids = self._current_selected_ids()
            comp_doc = self.res_window.comp_doc
            self._suspend_indicator = True
            try:
                for checkbox, f in self.all_pairs:
                    checkbox.IsChecked = (
                        getElementIdValue(comp_doc, f.Id) in preselected_ids
                    )
            finally:
                self._suspend_indicator = False
            self._refresh_indicators()
            self._sync_create_to_saved()
            self._update_save_enabled()
            self.show_filters()
        except Exception:
            self.res_window.report_error(u"רענון ההגדרות")

    # ------------------------------------------------------------------
    # Save (unified - covers both sub-pages)
    # ------------------------------------------------------------------
    def save_click(self, sender, e):
        try:
            filters_changed = self._filters_dirty()
            create_changed = self._create_dirty()
            if not (filters_changed or create_changed):
                return
            # Validate the filters selection before persisting anything.
            selected = None
            if filters_changed:
                selected = [
                    f for checkbox, f in self.all_pairs if checkbox.IsChecked
                ]
                if not selected:
                    self.res_window.notify(u"יש לבחור לפחות פילטר אחד.")
                    return
            # Create settings are cheap (future creations only) - save first.
            if create_changed:
                self.res_window.apply_create_settings(
                    self._current_create_settings()
                )
            # Filters change is heavy: resets the sheet cache + returns to Home.
            if filters_changed:
                self.res_window.apply_filter_selection(selected)
            self._update_save_enabled()
            self.res_window.notify(u"ההגדרות נשמרו.")
        except Exception:
            self.res_window.report_error(u"שמירת ההגדרות")
