# -*- coding: utf-8 -*-
""" Modeless results window for Get Bpm Sections - Frame + nav sidebar (R1).

Replaces the old StackPanel results dialog. This is the shell only: a header,
a left navigation column, and a <Frame> host. It opens on the
Home page and COMPUTES NOTHING (decision D1). The nav column (D8) is:

    Home       - fixed at top
    Settings   - fixed, below Home
    ---------- separator
    one button per sheet - inside a ScrollViewer

Sheet buttons are disabled until a valid discipline-filter selection exists
(decision D9). A sheet button navigates to a real DataGrid page
(SectionsSheetPage), created lazily and computed on first visit (R2). The
Settings button navigates to an in-window SectionsSettingsPage (D4); saving a
selection there refreshes the D6 cache key, drops computed pages, and unlocks
the sheets.

Modeled on DEV.extension CoordChecker's ResultsWindow (Frame + dynamic nav
buttons + active-page highlight). IronPython 2.7 / WPF; Hebrew only inside
string bodies. """

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from pyrevit.framework import wpf
from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent
from Autodesk.Revit.DB import Transaction
import os, sys, traceback

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
sys.path.append(os.path.dirname(__file__))

from pyrevit import forms
from pyrevit import script
from pyrevit.revit import events

import RevitUtils  # extension-level lib
import SectionsFilterSelection as sfs  # type: ignore
import SectionsScoring as scoring  # type: ignore
import SectionsCreate as creator  # type: ignore
from SectionsHomePage import SectionsHomePage  # type: ignore
from SectionsSheetPage import SectionsSheetPage  # type: ignore
from SectionsSettingsPage import SectionsSettingsPage  # type: ignore
from SectionsDisplay import SectionsDisplay  # type: ignore
import SectionsImage  # type: ignore

xaml_file = os.path.join(os.path.dirname(__file__), "SectionsResultsWindow.xaml")

# Envvar holding the single live window instance - the launcher's duplicate guard
# checks it so a second click never spins up a second dc3d server (section 6).
WINDOW_ENVVAR_KEY = "PYBPM_GETBPMSECTIONS_WINDOW"


class SystemRowItem(object):
    """Bindable row for one reference system in the details panel (S2). Built from
    a per-system record ({id, category, overlap, points, failed}) collected by
    SectionsScoring in S1. overlap/points are None for a system whose boolean op
    failed - shown as '?'. display_text is the toggle-button label (wired in S3)."""

    def __init__(self, record, enabled=False):
        self.system_id = int(record.get("id", -1))
        category = record.get("category")
        self.category = category if category else u"-"
        overlap = record.get("overlap")
        points = record.get("points")
        failed = record.get("failed")
        if failed or overlap is None:
            self.overlap_text = u"?"
        else:
            self.overlap_text = u"{:.0f}%".format(overlap * 100)
        if failed or points is None:
            self.points_text = u"?"
        else:
            self.points_text = u"{:.1f}".format(points)
        # S3 toggles this between "הצג" / "הסתר".
        self.display_text = u"הצג"
        # D2: the toggle button is enabled only when the host section exists.
        self.enabled = bool(enabled)


class SectionActionEventHandler(IExternalEventHandler):
    """Runs the queued Create / Delete / Go-to on Revit's API context (the same
    thread as the window), then lets the window refresh the affected page."""

    def __init__(self, window):
        self.window = window

    def Execute(self, uiapp):
        try:
            self.window.execute_pending_action(uiapp)
        except Exception as ex:
            print(ex)

    def GetName(self):
        return "BPM Get Bpm Sections Action"


class SectionsResultsWindow(Windows.Window):
    def __init__(self, uidoc, comp_link, comp_doc, filters, items, sheets):
        wpf.LoadComponent(self, xaml_file)

        self.uidoc = uidoc
        self.doc = uidoc.Document
        self.comp_link = comp_link
        self.comp_doc = comp_doc
        self.filters = filters  # list of ParameterFilterElements, or None
        self.items = items  # [{'section', 'sheet'}], no scoring
        self.sheets = sheets  # sorted unique sheet numbers

        # Selected discipline-filter id set - the D6 cache key component. Kept in
        # sync with self.filters (recomputed whenever the selection changes).
        self.filter_ids = self._compute_filter_ids(filters)

        self.active_page_background = Windows.Media.Brushes.LightBlue

        # sheet number -> its section views (for the lazy sheet pages, R2)
        self._sections_by_sheet = {}
        for it in self.items:
            self._sections_by_sheet.setdefault(it["sheet"], []).append(
                it["section"]
            )

        # Pages. Home + Settings are built once; sheet pages are created lazily
        # (there may be many sheets).
        self.home_page = SectionsHomePage(self)
        self.settings_page = SectionsSettingsPage(self)
        self._sheet_pages = {}  # sheet -> Page

        # Highlightable nav buttons (Home + Settings + sheets) - each maps to a
        # Frame page via btn.Tag and is highlighted when that page is shown.
        self.nav_buttons = []
        self.sheet_buttons = []  # list of (button, sheet)

        # External Event: every Revit write (create/delete/goto) runs through it.
        # _pending is a QUEUE - Revit coalesces rapid Raise() calls into a single
        # Execute, so a single slot would silently drop earlier requests.
        self._pending = []
        self._action_handler = SectionActionEventHandler(self)
        self._action_event = ExternalEvent.Create(self._action_handler)

        # Details side-panel state (S2): the row whose systems are shown, or None.
        self._details_row = None

        # dc3d display state (S3): the single-owner display server (created lazily)
        # and the system id currently drawn (None = nothing shown).
        self._display = None
        self._current_display_system_id = None
        # Set on window close so a display request still queued in the External
        # Event can't re-register a server after teardown (section 6 leak guard).
        self._closed = False

        # Section-image state (S4): a stable comp-model key for deterministic file
        # names, and the set of image files created this session (deleted on
        # close, D6). Old files are culled on open.
        self._comp_key = self._compute_comp_key(comp_doc)
        self._session_image_files = set()
        try:
            SectionsImage.cull_old_files()
        except Exception:
            pass

        self._build_nav()

        self.MainFrame.Content = self.home_page

        # Window close -> tear down the dc3d server and release the single-window
        # envvar so the tool can be reopened (section 6).
        self.Closed += self._on_window_closed

    # ------------------------------------------------------------------
    # Error handling - CRITICAL for a modeless pyRevit window
    # ------------------------------------------------------------------
    # This window is modeless (.Show()), so its event handlers run on Revit's
    # message loop with NO pyRevit exception wrapper around them. ANY exception
    # that escapes a handler propagates unhandled into Revit and crashes it
    # fatally (observed: an unhandled managed exception, ExceptionCode
    # 0xe0434352, took Revit down). Therefore EVERY event handler / callback
    # here MUST be wrapped in try/except and route to report_error.
    def report_error(self, context=u""):
        """Show the active exception (with full traceback) in a dialog instead
        of letting it escape a handler and crash Revit. Call only from inside an
        except block."""
        try:
            details = traceback.format_exc()
        except Exception:
            details = ""
        header = u"אירעה תקלה"
        if context:
            header = u"אירעה תקלה ב{}".format(context)
        try:
            self.Hide()
        except Exception:
            pass
        try:
            forms.alert(
                u"{}:\n\n{}".format(header, details), title="Get Bpm Sections"
            )
        except Exception:
            pass
        try:
            self.Show()
            self.Activate()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def has_filters(self):
        return bool(self.filters)

    def _compute_filter_ids(self, filters):
        """The selected filters' element-id ints (for the D6 cache key), or None
        when no selection exists yet."""
        if not filters:
            return None
        return [
            RevitUtils.getElementIdValue(self.comp_doc, f.Id) for f in filters
        ]

    def _compute_comp_key(self, comp_doc):
        """A stable ASCII-ish key identifying the comp model, for deterministic
        image file names. The comp model is a cloud link (get_model_info returns
        its modelGuid); fall back to its title if that ever fails."""
        try:
            return RevitUtils.get_model_info(comp_doc)["modelGuid"]
        except Exception:
            try:
                return comp_doc.Title
            except Exception:
                return "comp"

    # ------------------------------------------------------------------
    # Nav construction
    # ------------------------------------------------------------------
    def _make_nav_button(self, label, handler, bold=False):
        btn = Windows.Controls.Button()
        btn.Content = label
        btn.FlowDirection = Windows.FlowDirection.RightToLeft
        btn.HorizontalContentAlignment = Windows.HorizontalAlignment.Right
        btn.Margin = Windows.Thickness(2)
        btn.Padding = Windows.Thickness(6, 4, 6, 4)
        if bold:
            btn.FontWeight = Windows.FontWeights.Bold
        btn.Click += handler
        return btn

    def _make_separator(self):
        sep = Windows.Controls.Separator()
        sep.Margin = Windows.Thickness(0, 4, 0, 4)
        sep.Height = 2
        sep.Background = Windows.Media.Brushes.Gray
        return sep

    def _build_nav(self):
        # Home (fixed, top), highlighted as the default page.
        self.home_button = self._make_nav_button(
            u"ראשי", self.home_button_click, bold=True
        )
        self.home_button.Tag = self.home_page
        self.NavTopPanel.Children.Add(self.home_button)
        self.nav_buttons.append(self.home_button)

        # Settings (fixed, below Home) - highlighted like the other nav pages.
        self.settings_button = self._make_nav_button(
            u"הגדרות", self.settings_button_click
        )
        self.settings_button.Tag = self.settings_page
        self.NavTopPanel.Children.Add(self.settings_button)
        self.nav_buttons.append(self.settings_button)

        # Separator between the fixed top and the scrollable sheets (D8).
        self.NavTopPanel.Children.Add(self._make_separator())

        # One button per sheet, count = candidate sections on that sheet.
        counts = {}
        for it in self.items:
            counts[it["sheet"]] = counts.get(it["sheet"], 0) + 1

        enabled = self.has_filters()
        for sheet in self.sheets:
            label = u"{} ({})".format(
                sheet if sheet else u"-", counts.get(sheet, 0)
            )
            btn = self._make_nav_button(label, self._make_sheet_handler(sheet))
            btn.IsEnabled = enabled  # D9: locked until a valid selection exists
            self.NavSheetsPanel.Children.Add(btn)
            self.sheet_buttons.append((btn, sheet))
            self.nav_buttons.append(btn)

    def enable_sheet_buttons(self):
        """Unlock the sheet buttons (D9). Called after a valid discipline-filter
        selection is saved."""
        for btn, sheet in self.sheet_buttons:
            btn.IsEnabled = True
        self.home_page.update_content()

    def _reset_sheet_pages(self):
        """Drop any already-created sheet pages so they are rebuilt on next visit
        (used after the filter selection changes - D6). Their nav buttons lose
        their page Tag until recreated."""
        self._sheet_pages = {}
        for btn, sheet in self.sheet_buttons:
            btn.Tag = None

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def home_button_click(self, sender, e):
        try:
            self._on_navigate_away()  # D7
            self.MainFrame.Content = self.home_page
        except Exception:
            self.report_error(u"מעבר לדף הראשי")

    def _make_sheet_handler(self, sheet):
        def handler(sender, e):
            # open_sheet is fully guarded; this stays a thin dispatch.
            self.open_sheet(sheet)

        return handler

    def open_sheet(self, sheet):
        try:
            self._on_navigate_away()  # D7
            page = self._sheet_pages.get(sheet)
            if page is None:
                sections = self._sections_by_sheet.get(sheet, [])
                page = SectionsSheetPage(self, sheet, sections)
                self._sheet_pages[sheet] = page
                for btn, s in self.sheet_buttons:
                    if s == sheet:
                        btn.Tag = page
                        break
            # Lazy compute this sheet only, cache-served (D5). Runs once per page
            # (its _computed guard); a Settings change drops the page so a fresh
            # one recomputes with the new filters (D6). Navigate to the page ONLY
            # if the compute succeeded - showing a half-built page whose DataGrid
            # is in a bad state re-throws on the render path (uncaught) and
            # crashes Revit. On failure the error was already shown; stay on Home.
            if page.ensure_computed():
                self.MainFrame.Content = page
            else:
                self.MainFrame.Content = self.home_page
        except Exception:
            self.report_error(u"פתיחת גיליון")

    def MainFrame_Navigated(self, sender, e):
        try:
            for btn in self.nav_buttons:
                btn.Background = Windows.Media.Brushes.Transparent
            current_page = self.MainFrame.Content
            for btn in self.nav_buttons:
                if btn.Tag is not None and btn.Tag == current_page:
                    btn.Background = self.active_page_background
                    break
        except Exception:
            self.report_error(u"ניווט")

    # ------------------------------------------------------------------
    # Settings - in-window page (D4)
    # ------------------------------------------------------------------
    def settings_button_click(self, sender, e):
        try:
            self._on_navigate_away()  # D7
            # Re-sync the checkboxes to the saved selection so a prior visit's
            # unsaved edits are discarded, then show the page.
            self.settings_page.sync_to_current()
            self.MainFrame.Content = self.settings_page
        except Exception:
            self.report_error(u"הגדרות")

    def apply_filter_selection(self, selected):
        """Persist and activate a new discipline-filter selection (from the
        Settings page): save it, refresh the D6 cache key, drop computed sheet
        pages so they recompute with the new filters, unlock the sheet nav
        buttons (D9), and return to Home."""
        self._on_navigate_away()  # D7 - the filter change drops sheet pages too
        ids = [
            RevitUtils.getElementIdValue(self.comp_doc, f.Id) for f in selected
        ]
        sfs.save_selection(self.doc, self.comp_doc, ids)
        self.filters = selected
        self.filter_ids = self._compute_filter_ids(selected)
        self._reset_sheet_pages()
        self.enable_sheet_buttons()
        self.MainFrame.Content = self.home_page

    # ------------------------------------------------------------------
    # Details side-panel (S2)
    # ------------------------------------------------------------------
    def open_details(self, row, page=None):
        """Open the details panel for a section row: list its reference systems
        (the S1 per-system records). A cache record predating S1 lacks the
        'systems' field, so recompute that single section and re-read it. Wrapped
        - reached from a modeless Click handler."""
        try:
            if row is None:
                return
            # Opening details for a (possibly different) section clears any system
            # currently drawn (D7/D8) - fresh rows default to the "הצג" state.
            self.request_hide()
            record = row.result
            systems = record.get("systems") if record else None
            if systems is None and page is not None:
                # Pre-S1 record: recompute this one section, then re-read it from
                # the (now updated) cache - recompute rebuilds the row objects, so
                # the passed `row` is stale for the record but still valid as the
                # section reference.
                page.recompute([row.section])
                section_id = scoring.section_id_value(self.comp_doc, row.section)
                record = page._score_cache.get(section_id)
                systems = record.get("systems") if record else None
            if systems is None:
                systems = []
            self._details_row = row
            header = record.get("section_name", u"") if record else u""
            self.DetailsHeader.Text = header if header else u"פרטי חתך"
            self.SystemsDataGrid.Items.Clear()
            enabled = bool(getattr(row, "exists", False))  # D2
            for sys_record in systems:
                self.SystemsDataGrid.Items.Add(SystemRowItem(sys_record, enabled))
            # UX hints (S5): empty-state + "create the section first" when it does
            # not exist yet (the toggle buttons are disabled until then).
            self.DetailsEmptyHint.Visibility = (
                Windows.Visibility.Visible
                if not systems
                else Windows.Visibility.Collapsed
            )
            self.DetailsExistsHint.Visibility = (
                Windows.Visibility.Collapsed
                if (enabled or not systems)
                else Windows.Visibility.Visible
            )
            self._load_details_image()
            self.open_details_pane()
        except Exception:
            self.report_error(u"פתיחת פרטים")

    def open_details_pane(self):
        """Expand the details columns ([3] divider + [4] pane)."""
        self.RootGrid.ColumnDefinitions[3].Width = Windows.GridLength(1)
        self.RootGrid.ColumnDefinitions[4].Width = Windows.GridLength(340)

    def close_details_pane(self):
        """Collapse the details columns, switch off any dc3d display (D7), and
        drop the tracked row."""
        self.request_hide()
        self.RootGrid.ColumnDefinitions[3].Width = Windows.GridLength(0)
        self.RootGrid.ColumnDefinitions[4].Width = Windows.GridLength(0)
        self._details_row = None

    def CloseDetails_Click(self, sender, e):
        try:
            self.close_details_pane()
        except Exception:
            self.report_error(u"סגירת פרטים")

    def _resync_details_exists(self):
        """Re-sync the OPEN details pane after an in-place exists refresh
        (Create/Delete): update the D2 toggle-enable + the empty/exists hints, and
        hide a lingering overlay if the host section was just deleted. No-op if the
        panel is closed. Runs on the API context (from execute_pending_action)."""
        if self._details_row is None:
            return
        try:
            enabled = bool(getattr(self._details_row, "exists", False))
            has_items = False
            for item in self.SystemsDataGrid.Items:
                has_items = True
                try:
                    item.enabled = enabled
                except Exception:
                    pass
            # Section deleted while a system was shown -> hide the overlay so it
            # doesn't linger with no host section.
            if not enabled and self._current_display_system_id is not None:
                self.request_hide()
                for item in self.SystemsDataGrid.Items:
                    try:
                        item.display_text = u"הצג"
                    except Exception:
                        pass
            self.SystemsDataGrid.Items.Refresh()
            self.DetailsEmptyHint.Visibility = (
                Windows.Visibility.Collapsed
                if has_items
                else Windows.Visibility.Visible
            )
            self.DetailsExistsHint.Visibility = (
                Windows.Visibility.Collapsed
                if (enabled or not has_items)
                else Windows.Visibility.Visible
            )
        except Exception:
            pass

    def _on_navigate_away(self):
        """D7: leaving the current sheet/page closes the details panel (and, via
        close_details_pane, switches off the dc3d display)."""
        try:
            self.close_details_pane()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # dc3d display (S3) - the single-owner server lives on the window; every
    # Revit op runs through the External Event (funnelled with the row actions).
    # ------------------------------------------------------------------
    def _get_display(self):
        if self._display is None:
            self._display = SectionsDisplay(
                self.uidoc, self.comp_doc, self.comp_link
            )
        return self._display

    def request_display(self, system_id, section_name):
        """Enqueue a 'show this system' request and raise the External Event."""
        try:
            self._pending.append(
                {
                    "action": "display",
                    "system_id": int(system_id),
                    "section_name": section_name,
                }
            )
            self._current_display_system_id = int(system_id)
            self._action_event.Raise()
        except Exception:
            self.report_error(u"תצוגת מערכת")

    def request_hide(self):
        """Enqueue a 'hide' request (no-op downstream if nothing is shown)."""
        try:
            self._current_display_system_id = None
            self._pending.append({"action": "hide"})
            self._action_event.Raise()
        except Exception:
            pass

    def ToggleSystemDisplay_Click(self, sender, e):
        try:
            sys_row = sender.DataContext
            if sys_row is None:
                return
            # D2: display happens in the host section, so it must exist.
            if self._details_row is None or not getattr(
                self._details_row, "exists", False
            ):
                self.notify(u"צור את החתך תחילה כדי להציג את המערכת")
                return
            if self._current_display_system_id == sys_row.system_id:
                # Already shown -> toggle off.
                self.request_hide()
                sys_row.display_text = u"הצג"
            else:
                self.request_display(
                    sys_row.system_id, self._details_row.section_name
                )
                for item in self.SystemsDataGrid.Items:
                    try:
                        item.display_text = (
                            u"הסתר"
                            if item.system_id == sys_row.system_id
                            else u"הצג"
                        )
                    except Exception:
                        pass
            self.SystemsDataGrid.Items.Refresh()
        except Exception:
            self.report_error(u"תצוגת מערכת")

    def _on_window_closed(self, sender, e):
        """Tear down the dc3d server and release the single-window envvar.

        remove_server mutates the ExternalService registry the Draw Thread reads,
        so it MUST run on the Revit API context - defer it via
        execute_in_revit_context (the ViewRange reference pattern), NOT inline on
        this UI-thread Closed handler. First flip _closed and drop the pending
        queue so any display request still in flight can't re-register a server
        after teardown."""
        self._closed = True
        self._pending = []
        try:
            if self._display is not None:
                events.execute_in_revit_context(self._display.shutdown)
        except Exception:
            # Fallback: if scheduling fails, remove directly (best effort).
            try:
                if self._display is not None:
                    self._display.shutdown()
            except Exception:
                pass
        try:
            SectionsImage.delete_files(list(self._session_image_files))
        except Exception:
            pass
        try:
            script.set_envvar(WINDOW_ENVVAR_KEY, None)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Section image (S4) - exported from the compilation model, cached per
    # (comp model, section) under a deterministic temp path.
    # ------------------------------------------------------------------
    def _current_image_path(self):
        """Deterministic PNG path for the section shown in the details panel, or
        None when no panel/section is active."""
        if self._details_row is None:
            return None
        section = getattr(self._details_row, "section", None)
        if section is None:
            return None
        section_id = RevitUtils.getElementIdValue(self.comp_doc, section.Id)
        return SectionsImage.deterministic_path(self._comp_key, section_id)

    def _load_image_into(self, path):
        """Load a PNG into the details Image control as a frozen, OnLoad bitmap so
        the file is NOT locked (allows later delete/refresh)."""
        from System import Uri
        from System.Windows.Media.Imaging import BitmapImage, BitmapCacheOption

        bmp = BitmapImage()
        bmp.BeginInit()
        bmp.CacheOption = BitmapCacheOption.OnLoad
        bmp.UriSource = Uri(path)
        bmp.EndInit()
        bmp.Freeze()
        self.DetailsImage.Source = bmp
        self._session_image_files.add(path)

    def _load_details_image(self):
        """Show the section's cached image if present; otherwise clear the control
        (the planner uses 'הצג תמונה' to export). Never fatal."""
        try:
            self.DetailsImage.Source = None
            path = self._current_image_path()
            if path and os.path.exists(path):
                self._load_image_into(path)
        except Exception:
            try:
                self.DetailsImage.Source = None
            except Exception:
                pass

    def _request_export_image(self):
        """Enqueue an image export (runs on the API context) for the current
        section."""
        try:
            if self._details_row is None:
                return
            section = getattr(self._details_row, "section", None)
            path = self._current_image_path()
            if section is None or path is None:
                return
            self._pending.append(
                {"action": "export_image", "section": section, "dest": path}
            )
            self._action_event.Raise()
        except Exception:
            self.report_error(u"ייצוא תמונה")

    def ShowImage_Click(self, sender, e):
        try:
            path = self._current_image_path()
            if path is None:
                return
            if os.path.exists(path):
                self._load_image_into(path)
            else:
                self._request_export_image()
        except Exception:
            self.report_error(u"הצגת תמונה")

    def RefreshImage_Click(self, sender, e):
        try:
            path = self._current_image_path()
            if path is None:
                return
            # Release the WPF handle, drop the cached PNG, then re-export.
            try:
                self.DetailsImage.Source = None
            except Exception:
                pass
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
            self._request_export_image()
        except Exception:
            self.report_error(u"רענון תמונה")

    def ShowImageLarge_Click(self, sender, e):
        try:
            path = self._current_image_path()
            if path and os.path.exists(path):
                from System.Diagnostics import Process

                Process.Start(path)  # default Windows image viewer (D5)
            else:
                self.notify(u"אין תמונה להצגה - לחץ 'הצג תמונה' תחילה")
        except Exception:
            self.report_error(u"הצגת תמונה בגדול")

    def notify(self, message):
        """Show a plain info message from a modeless-safe context."""
        try:
            self.Hide()
            forms.alert(message, title="Get Bpm Sections")
            self.Show()
            self.Activate()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Row actions (R3) - all Revit writes go through the External Event.
    # ------------------------------------------------------------------
    def _confirm(self, message):
        self.Hide()
        result = forms.alert(message, yes=True, no=True)
        self.Show()
        self.Activate()
        return result

    def request_action(self, action, rows):
        """Enqueue a Create / Delete / Go-to for the given rows (SectionsRowItem)
        and raise the External Event. Any UI prompt (section type, delete confirm)
        happens here on the UI thread BEFORE the API context runs. Wrapped because
        this is reached from a modeless handler."""
        try:
            if not rows:
                return
            if action == "create":
                targets = [row for row in rows if not row.exists]
                if not targets:
                    return
                type_id = creator.get_type_id(self.doc)  # may prompt (UI thread)
                self.Activate()
                if not type_id:
                    return
                for row in targets:
                    self._pending.append(
                        {
                            "action": "create",
                            "name": row.section_name,
                            "section": row.section,
                            "type_id": type_id,
                        }
                    )
            elif action == "delete":
                targets = [row for row in rows if row.exists]
                if not targets:
                    return
                if len(targets) == 1:
                    prompt = u"למחוק את החתך '{}'?".format(
                        creator.target_section_name(targets[0].section_name)
                    )
                else:
                    prompt = u"למחוק {} חתכים?".format(len(targets))
                if not self._confirm(prompt):  # one confirm for N rows (7.3)
                    return
                for row in targets:
                    self._pending.append(
                        {"action": "delete", "name": row.section_name}
                    )
            elif action == "goto":
                existing = [row for row in rows if row.exists]
                if not existing:
                    return
                # Go-to acts on a single view - the first existing target.
                self._pending.append(
                    {"action": "goto", "name": existing[0].section_name}
                )
            else:
                return
            self._action_event.Raise()
        except Exception:
            self.report_error(u"פעולה על חתך")

    def execute_pending_action(self, uiapp):
        """Runs on Revit's API context (via the External Event). Drains the whole
        queue - Revit coalesces rapid Raise() calls into a single Execute."""
        requests = self._pending
        self._pending = []
        if self._closed:
            # Window is closing/closed - never (re-)touch the model or register a
            # server from a late-firing Execute. Teardown is handled separately.
            return
        changed = False
        for request in requests:
            try:
                if self._run_action(uiapp, request):
                    changed = True
            except Exception as ex:
                print(ex)
        if changed:
            # Refresh every already-built sheet page: a coalesced Execute may
            # carry actions from more than one sheet, and a created/deleted view
            # only affects the page holding that section anyway.
            for page in self._sheet_pages.values():
                try:
                    if page.items:
                        page.refresh_exists()
                except Exception as ex:
                    print(ex)
            # refresh_exists updated _details_row.exists in place - re-sync the
            # open details pane so the D2 toggle buttons + hint reflect it without
            # a reopen.
            self._resync_details_exists()

    def _run_action(self, uiapp, request):
        """Perform one action. Returns True if an exists-state may have changed.
        Every Transaction is always closed (commit or rollback)."""
        action = request["action"]

        # dc3d display/hide (S3) - no exists-state change, so return False. These
        # never open a transaction (DirectContext3D draws outside the model).
        if action == "display":
            self._get_display().show_system(
                uiapp, request["system_id"], request["section_name"]
            )
            return False
        if action == "hide":
            if self._display is not None:
                self._display.clear(uiapp)
            return False
        if action == "export_image":
            # ExportImage is read-only (no transaction). Execute runs on the main
            # UI thread, so loading the result into the WPF Image control here is
            # safe - but only if the panel still shows the section it was for.
            dest = None
            try:
                dest = SectionsImage.export_section_image(
                    self.comp_doc, request["section"], request["dest"]
                )
            except Exception as ex:
                print(ex)
            if dest:
                try:
                    if self._current_image_path() == dest:
                        self._load_image_into(dest)
                    else:
                        self._session_image_files.add(dest)
                except Exception:
                    pass
            else:
                # Clean no-op failure (e.g. Revit wrote nothing) - tell the user,
                # otherwise the panel just stays blank with no explanation.
                try:
                    self.notify(u"ייצוא התמונה נכשל")
                except Exception:
                    pass
            return False

        name = request["name"]

        if action == "create":
            # Never create a second, suffixed copy: Create is valid only while the
            # exact name is free. Re-check here in case a stale click got through.
            if creator.find_existing_section(self.doc, name) is not None:
                return True
            comp_section = request["section"]
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
