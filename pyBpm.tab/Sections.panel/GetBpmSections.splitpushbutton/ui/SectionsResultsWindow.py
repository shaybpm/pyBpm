# -*- coding: utf-8 -*-
""" Modeless results window for Get Bpm Sections - Frame + nav sidebar (R1).

Replaces the old StackPanel dialog (SectionsResultsDialog). This is the shell
only: a header, a left navigation column, and a <Frame> host. It opens on the
Home page and COMPUTES NOTHING (decision D1). The nav column (D8) is:

    Home       - fixed at top
    Settings   - fixed, below Home
    ---------- separator
    one button per sheet - inside a ScrollViewer

Sheet buttons are disabled until a valid discipline-filter selection exists
(decision D9). The per-sheet DataGrid pages arrive in R2; here a sheet button
navigates to a light placeholder page. The Settings button (R1) bridges to the
existing modal FilterSelectionDialog via SectionsFilterSelection; R4 turns it
into an in-window page.

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
import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
sys.path.append(os.path.dirname(__file__))

from pyrevit import forms

import SectionsFilterSelection as sfs  # type: ignore
from SectionsHomePage import SectionsHomePage  # type: ignore

xaml_file = os.path.join(os.path.dirname(__file__), "SectionsResultsWindow.xaml")


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

        self.active_page_background = Windows.Media.Brushes.LightBlue

        # sheet number -> its section views (for the lazy sheet pages, R2)
        self._sections_by_sheet = {}
        for it in self.items:
            self._sections_by_sheet.setdefault(it["sheet"], []).append(
                it["section"]
            )

        # Pages. Home is built once; sheet pages are created lazily (R2 will
        # make them real DataGrid pages - there may be many sheets).
        self.home_page = SectionsHomePage(self)
        self._sheet_pages = {}  # sheet -> Page

        # Highlightable nav buttons (Home + sheets). Settings opens a modal, so
        # it is never a Frame page and is not in this list.
        self.nav_buttons = []
        self.sheet_buttons = []  # list of (button, sheet)

        self._build_nav()

        self.MainFrame.Content = self.home_page

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def has_filters(self):
        return bool(self.filters)

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
            u"דף ראשי", self.home_button_click, bold=True
        )
        self.home_button.Tag = self.home_page
        self.NavTopPanel.Children.Add(self.home_button)
        self.nav_buttons.append(self.home_button)

        # Settings (fixed, below Home).
        self.settings_button = self._make_nav_button(
            u"דף הגדרות", self.settings_button_click
        )
        self.NavTopPanel.Children.Add(self.settings_button)

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
        self.MainFrame.Content = self.home_page

    def _make_sheet_handler(self, sheet):
        def handler(sender, e):
            self.open_sheet(sheet)

        return handler

    def open_sheet(self, sheet):
        page = self._sheet_pages.get(sheet)
        if page is None:
            page = self._create_sheet_placeholder(sheet)
            self._sheet_pages[sheet] = page
            for btn, s in self.sheet_buttons:
                if s == sheet:
                    btn.Tag = page
                    break
        self.MainFrame.Content = page

    def _create_sheet_placeholder(self, sheet):
        """R1 placeholder page for a sheet. R2 replaces this with a real
        SectionsSheetPage DataGrid."""
        page = Windows.Controls.Page()
        page.Title = sheet if sheet else u"-"
        panel = Windows.Controls.StackPanel()
        panel.FlowDirection = Windows.FlowDirection.RightToLeft
        panel.Margin = Windows.Thickness(18)
        count = len(self._sections_by_sheet.get(sheet, []))
        text_block = Windows.Controls.TextBlock()
        text_block.FontSize = 14
        text_block.TextWrapping = Windows.TextWrapping.Wrap
        text_block.Text = (
            u"גיליון {} - {} חתכים. טבלת ההתאמה תתווסף בשלב הבא."
        ).format(sheet if sheet else u"-", count)
        panel.Children.Add(text_block)
        page.Content = panel
        return page

    def MainFrame_Navigated(self, sender, e):
        for btn in self.nav_buttons:
            btn.Background = Windows.Media.Brushes.Transparent
        current_page = self.MainFrame.Content
        for btn in self.nav_buttons:
            if btn.Tag is not None and btn.Tag == current_page:
                btn.Background = self.active_page_background
                break

    # ------------------------------------------------------------------
    # Settings (R1 bridge to the existing modal dialog; R4 -> in-window page)
    # ------------------------------------------------------------------
    def settings_button_click(self, sender, e):
        try:
            result = sfs.ensure_filter_selection(self.doc, force_window=True)
        except Exception as ex:
            print(ex)
            self.Activate()
            return
        self.Activate()
        status = result.get("status")
        if status == "blocked":
            self.Hide()
            forms.alert(result.get("message", u"לא ניתן לשמור בחירת פילטרים."))
            self.Show()
            return
        if status != "ok":
            return
        self.filters = result["filters"]
        # A changed selection invalidates any computed sheet pages (D6). No cache
        # is used yet in R1, but reset the pages so R2's real pages recompute.
        self._reset_sheet_pages()
        self.MainFrame.Content = self.home_page
        self.enable_sheet_buttons()
