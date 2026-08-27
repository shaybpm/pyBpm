# -*- coding: utf-8 -*-
"""The planner-facing Visual Inspection dashboard.

Shows how the coordinator's Arc-Const inspection scored this project, sheet by
sheet and view by view, and lets the planner rebuild any of those views in
their own model so they can go and fix what scored badly.

Ordered WORST FIRST throughout. The dashboard exists to find gaps; a list that
opens on the levels already passing makes a planner scroll past their own good
news to reach the work.

Modeless, so the planner can keep working with it open - which is also why
every model write goes through an ExternalEvent: a modeless window is not in
Revit's API context and calling the API from a WPF handler would throw.

Element lifetime (see the revit-element-lifetime rule): nothing here holds a
live Element or Document across a click. The comp link's ElementId is the
anchor - it lives in the HOST document and survives a link reload - and the
comp Document, the comp views and the report are all re-resolved from it. The
report is data, not handles: it is read afresh on every refresh.
"""

import os

from pyrevit.framework import wpf
from System import Windows

from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent

import RevitUtils  # extension-level lib
import VisualInspectionRead as read  # type: ignore
import VisualInspectionMirror as mirror  # type: ignore


xaml_file = os.path.join(os.path.dirname(__file__), "VisualInspectionWindow.xaml")

WINDOW_ENVVAR_KEY = "bpm_visual_inspection_window"

GRAY = Windows.Media.Brushes.Gray
BLACK = Windows.Media.Brushes.Black
RED = Windows.Media.Brushes.Firebrick
ORANGE = Windows.Media.Brushes.DarkOrange
GREEN = Windows.Media.Brushes.SeaGreen

# Where a score stops being a warning and starts being a problem. Deliberately
# coarse: the number is a similarity measure, not a grade, and pretending to
# finer resolution than that would be false precision.
SCORE_BAD = 60.0
SCORE_GOOD = 85.0


def score_brush(score):
    if score is None:
        return GRAY
    if score < SCORE_BAD:
        return RED
    if score < SCORE_GOOD:
        return ORANGE
    return GREEN


def score_text(score):
    if score is None:
        return u"—"
    return u"{0:.0f}".format(score)


class ActionEventHandler(IExternalEventHandler):
    """Runs the queued create / sync on Revit's API context."""

    def __init__(self, window):
        self.window = window

    def Execute(self, uiapp):
        try:
            self.window.execute_pending(uiapp)
        except Exception as ex:
            self.window.set_status(u"הפעולה נכשלה: {0}".format(ex), RED)

    def GetName(self):
        return "BPM Visual Inspection Action"


class VisualInspectionWindow(Windows.Window):
    def __init__(self, uidoc, comp_link):
        wpf.LoadComponent(self, xaml_file)

        self.uidoc = uidoc
        self.doc = uidoc.Document
        self._comp_link_id = RevitUtils.getElementIdValue(self.doc, comp_link.Id)
        self._closed = False

        # A QUEUE, not a slot: Revit coalesces rapid Raise() calls into a single
        # Execute, so a single slot would silently drop the earlier request.
        self._pending = []
        self._event = ExternalEvent.Create(ActionEventHandler(self))

        self.Closed += self._on_closed
        self.reload()

    # --- LIVE HANDLES ---------------------------------------------------------

    @property
    def comp_link(self):
        """Re-resolved every time. The instance lives in the host document."""
        link = self.doc.GetElement(
            RevitUtils.getElementId(self.doc, self._comp_link_id)
        )
        if link is None or not RevitUtils.is_valid(link):
            return None
        return link

    @property
    def comp_doc(self):
        link = self.comp_link
        if link is None:
            return None
        return link.GetLinkDocument()

    # --- BUILDING THE LIST ----------------------------------------------------

    def reload(self):
        """Read the compilation model again and rebuild the whole list."""
        self.rows_panel.Children.Clear()

        comp_doc = self.comp_doc
        if comp_doc is None:
            self.comp_model_text.Text = read.COMP_LINK_BROKEN_MSG
            self.model_score_text.Text = u"—"
            return

        report = read.read_inspection(comp_doc)
        existing = mirror.mirrored_names(self.doc)

        self.comp_model_text.Text = u"מודל הקומפילציה: {0}".format(comp_doc.Title)
        self.model_score_text.Text = score_text(report.model_score)
        self.model_score_text.Foreground = score_brush(report.model_score)
        self.run_date_text.Text = (
            u"נבדק לאחרונה: {0}".format(report.run_date)
            if report.run_date
            else u"אין תאריך בדיקה"
        )
        self.source_note_text.Text = self._source_note(report)

        if report.is_empty:
            self.rows_panel.Children.Add(
                self._note(
                    u"לא נמצאו מבטים של בדיקה ויזואלית במודל הקומפילציה. "
                    u"ייתכן שהבדיקה עדיין לא הורצה על הפרויקט הזה."
                )
            )
            return

        for sheet in report.sheets:
            self.rows_panel.Children.Add(self._sheet_header(sheet))
            for view in sheet.views:
                self.rows_panel.Children.Add(self._view_row(view, existing))

        if report.loose_views:
            self.rows_panel.Children.Add(
                self._note(
                    u"מבטים שאינם על גיליון ({0}) — נוצרו אך טרם שובצו."
                    .format(len(report.loose_views))
                )
            )
            for view in report.loose_views:
                self.rows_panel.Children.Add(self._view_row(view, existing))

    def _source_note(self, report):
        if report.source == "revision":
            return (
                u"הציון נקרא מהמהדורה שעל הגיליון. במודל הקומפילציה לא הוגדרו "
                u"הפרמטרים BPM_VI_Score / BPM_VI_RunDate, ולכן אין ציון לכל מבט "
                u"בנפרד — רק ציון כולל."
            )
        if report.source is None:
            return u"לא נמצא ציון במודל הקומפילציה."
        return u""

    # --- ROWS -----------------------------------------------------------------

    def _sheet_header(self, sheet):
        border = Windows.Controls.Border()
        border.Background = Windows.Media.Brushes.WhiteSmoke
        border.BorderBrush = GRAY
        border.BorderThickness = Windows.Thickness(0, 0, 0, 1)
        border.Padding = Windows.Thickness(8, 6, 8, 6)
        border.Margin = Windows.Thickness(0, 10, 0, 0)

        grid = self._grid([70, 110, 300, 130])
        grid.Children.Add(
            self._cell(score_text(sheet.score), 0, bold=True, brush=score_brush(sheet.score))
        )
        grid.Children.Add(self._cell(sheet.number or u"—", 1, bold=True))
        grid.Children.Add(self._cell(sheet.name or u"", 2, bold=True))
        grid.Children.Add(self._cell(sheet.run_date or u"", 3, brush=GRAY))
        border.Child = grid
        return border

    def _view_row(self, view, existing):
        grid = self._grid([70, 110, 300, 130, 110])
        grid.Margin = Windows.Thickness(0, 2, 0, 2)

        grid.Children.Add(
            self._cell(score_text(view.score), 0, brush=score_brush(view.score))
        )
        grid.Children.Add(self._cell(view.kind, 1, brush=GRAY))
        grid.Children.Add(self._cell(view.name or u"", 2))
        grid.Children.Add(self._cell(view.detail_number or u"", 3, brush=GRAY))

        is_here = view.name in existing
        button = Windows.Controls.Button()
        button.Content = u"סנכרן" if is_here else u"צור אצלי"
        button.Padding = Windows.Thickness(6, 2, 6, 2)
        button.Tag = (view.view_id, view.name, is_here)
        button.Click += self._action_click
        if view.kind != u"חתך":
            # Plans are shown - the planner should see their score - but they
            # cannot be rebuilt yet, and a button that always fails is worse
            # than one that says so up front.
            button.IsEnabled = False
            button.ToolTip = mirror.MIRROR_UNSUPPORTED_PLAN
        Windows.Controls.Grid.SetColumn(button, 4)
        grid.Children.Add(button)
        return grid

    def _grid(self, widths):
        grid = Windows.Controls.Grid()
        for width in widths:
            column = Windows.Controls.ColumnDefinition()
            column.Width = Windows.GridLength(width)
            grid.ColumnDefinitions.Add(column)
        return grid

    def _cell(self, text, column, bold=False, brush=None):
        block = Windows.Controls.TextBlock()
        block.Text = text
        block.Margin = Windows.Thickness(4, 2, 4, 2)
        block.VerticalAlignment = Windows.VerticalAlignment.Center
        block.TextTrimming = Windows.TextTrimming.CharacterEllipsis
        if bold:
            block.FontWeight = Windows.FontWeights.Bold
        block.Foreground = brush or BLACK
        Windows.Controls.Grid.SetColumn(block, column)
        return block

    def _note(self, text):
        block = Windows.Controls.TextBlock()
        block.Text = text
        block.TextWrapping = Windows.TextWrapping.Wrap
        block.Foreground = GRAY
        block.Margin = Windows.Thickness(4, 12, 4, 4)
        return block

    # --- ACTIONS --------------------------------------------------------------

    def _action_click(self, sender, e):
        view_id, view_name, is_here = sender.Tag
        self._pending.append(
            {"view_id": view_id, "view_name": view_name, "sync": is_here}
        )
        self.set_status(
            u"מסנכרן..." if is_here else u"יוצר את המבט אצלך...", GRAY
        )
        self._event.Raise()

    def execute_pending(self, uiapp):
        """Runs on Revit's API context. Drains the whole queue."""
        from Autodesk.Revit.DB import Transaction

        pending, self._pending = self._pending, []
        if not pending:
            return

        comp_link = self.comp_link
        comp_doc = self.comp_doc
        if comp_doc is None:
            self.set_status(read.COMP_LINK_BROKEN_MSG, RED)
            return
        transform = comp_link.GetTotalTransform()

        done = []
        failed = []
        transaction = Transaction(self.doc, "pyBpm | Visual Inspection - mirror view")
        transaction.Start()
        try:
            for item in pending:
                ok, message = self._run_one(item, comp_doc, transform)
                (done if ok else failed).append(message)
            transaction.Commit()
        except Exception:
            if transaction.HasStarted() and not transaction.HasEnded():
                transaction.RollBack()
            raise

        self.reload()
        if failed:
            self.set_status(u" · ".join(failed), RED)
        else:
            self.set_status(u" · ".join(done), GREEN)

    def _run_one(self, item, comp_doc, transform):
        """(succeeded, message) for one queued action."""
        comp_view = comp_doc.GetElement(
            RevitUtils.getElementId(comp_doc, item["view_id"])
        )
        if comp_view is None:
            return False, u"המבט '{0}' כבר אינו קיים בקומפילציה.".format(
                item["view_name"]
            )

        if item["sync"]:
            existing = mirror.find_mirrored_view(self.doc, item["view_name"])
            if existing is None:
                # It was there when the list was drawn and is not there now.
                # Creating it instead is what the planner wanted either way.
                item["sync"] = False
            else:
                ok, error = mirror.resync_section(
                    self.doc, existing, comp_view, transform
                )
                if not ok:
                    return False, error
                return True, u"'{0}' סונכרן למיקום שבקומפילציה.".format(
                    item["view_name"]
                )

        view, error = mirror.mirror_section(self.doc, comp_view, transform)
        if error:
            return False, error
        return True, u"נוצר אצלך המבט '{0}'.".format(view.Name)

    # --- CHROME ---------------------------------------------------------------

    def set_status(self, text, brush=None):
        self.status_text.Text = text
        self.status_text.Foreground = brush or BLACK

    def refresh_btn_Click(self, sender, e):
        self.reload()
        self.set_status(u"", BLACK)

    def close_btn_Click(self, sender, e):
        self.Close()

    def _on_closed(self, sender, e):
        self._closed = True
