# -*- coding: utf-8 -*-
"""The planner-facing Visual Inspection dashboard - shell, navigation, writes.

Shows how the coordinator's Arc-Const inspection scored this project and lets
the planner rebuild any of those views in their own model, drawn the way the
compilation drew them, so they can go and fix what scored badly.

Structure follows GetBpmSections: a header, a left navigation column with one
button per inspection ROW, and a <Frame> hosting one page per row. A row is a
sheet's worth of views, and each page is a DataGrid of them. Ordered WORST
FIRST throughout, both the nav buttons and the rows inside a page.

Modeless, so the planner can keep working with it open - which is also why
every model write goes through an ExternalEvent: a modeless window is not in
Revit's API context and calling the API from a WPF handler would throw.

Element lifetime (see the revit-element-lifetime rule): nothing here holds a
live Element or Document across a click. The comp link's ElementId is the
anchor - it lives in the HOST document and survives a link reload - and the
comp Document, the comp views and the report are all re-resolved from it.
"""

import os
import sys

from pyrevit.framework import wpf
from System import Windows

from Autodesk.Revit.DB import Transaction
from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
sys.path.append(os.path.dirname(__file__))

import RevitUtils  # extension-level lib
import VisualInspectionRead as read  # type: ignore
import VisualInspectionMirror as mirror  # type: ignore
import VisualInspectionTemplate as templates  # type: ignore
from VisualInspectionRowPage import (  # type: ignore
    KIND_PLAN,
    VisualInspectionRowPage,
    ViewRowItem,
    score_brush,
    score_text,
)


xaml_file = os.path.join(os.path.dirname(__file__), "VisualInspectionWindow.xaml")

WINDOW_ENVVAR_KEY = "bpm_visual_inspection_window"

GRAY = Windows.Media.Brushes.Gray
BLACK = Windows.Media.Brushes.Black
RED = Windows.Media.Brushes.Firebrick
GREEN = Windows.Media.Brushes.SeaGreen

ACTIVE_NAV_BACKGROUND = Windows.Media.SolidColorBrush(
    Windows.Media.Color.FromRgb(207, 226, 245)
)
NAV_BUTTON_MAX_WIDTH = 260


def _sheet_label(sheet):
    """How one inspection sheet is named in the list: "V103 · Level 3".

    The sheet is the unit this dashboard is organised by - one nav entry, one
    page - so it is worth naming the way the coordinator who made it does,
    which is by its number. `_LooseGroup` (views on no sheet) has no number and
    falls back to its own title.
    """
    number = getattr(sheet, "number", None)
    name = getattr(sheet, "name", None)
    if number and name:
        return u"{0} · {1}".format(number, name)
    return number or name or u"—"


class ActionEventHandler(IExternalEventHandler):
    """Runs the queued create / sync work on Revit's API context."""

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
        # "Create all" pushes a whole row's worth at once and relies on it.
        self._pending = []
        self._event = ExternalEvent.Create(ActionEventHandler(self))

        self._nav_buttons = []
        self._pages = {}

        # comp level id -> the planner's level id, for the levels where the
        # elevation match was ambiguous and they had to choose. Window-scoped
        # on purpose: it is a working session's answer, not a project setting,
        # and a stale mapping remembered across weeks would be worse than the
        # question.
        self._level_choice = {}

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

    # --- READING AND BUILDING -------------------------------------------------

    def reload(self):
        """Read the compilation model again and rebuild the whole dashboard."""
        remembered = self._active_key()

        self.nav_panel.Children.Clear()
        self._nav_buttons = []
        self._pages = {}
        self.main_frame.Content = None

        comp_doc = self.comp_doc
        if comp_doc is None:
            self._show_empty(read.COMP_LINK_BROKEN_MSG)
            self.model_score_text.Text = u"—"
            self.comp_model_text.Text = read.COMP_LINK_BROKEN_MSG
            return

        report = read.read_inspection(comp_doc)
        self._render_header(report, comp_doc)

        if report.is_empty:
            self._show_empty(
                u"לא נמצאו מבטים של בדיקה ויזואלית במודל הקומפילציה. "
                u"ייתכן שהבדיקה עדיין לא הורצה על הפרויקט הזה."
            )
            return

        existing = mirror.mirrored_names(self.doc)
        # One cache for the whole rebuild: every section of a row shares a
        # template, and comparing one means walking all of its filters.
        template_cache = {}

        groups = []
        for sheet in report.sheets:
            groups.append((sheet, sheet.views))
        if report.loose_views:
            groups.append((_LooseGroup(report.loose_views), report.loose_views))

        for sheet, entries in groups:
            items = [
                self._row_item(entry, existing, comp_doc, template_cache)
                for entry in entries
            ]
            self._add_nav_button(sheet, items)

        self.empty_hint.Visibility = Windows.Visibility.Collapsed
        self._restore_or_open_first(remembered)

    def _row_item(self, entry, existing, comp_doc, template_cache):
        name, state, differences = None, templates.STATE_NONE, []
        comp_view = comp_doc.GetElement(
            RevitUtils.getElementId(comp_doc, entry.view_id)
        )
        if comp_view is not None:
            name, state, differences = templates.template_status(
                self.doc, comp_view, template_cache
            )
        return ViewRowItem(
            entry, entry.name in existing, state, differences, name
        )

    def _render_header(self, report, comp_doc):
        self.comp_model_text.Text = u"מודל הקומפילציה: {0}".format(comp_doc.Title)
        self.model_score_text.Text = score_text(report.model_score)
        self.model_score_text.Foreground = score_brush(report.model_score)
        self.run_date_text.Text = (
            u"נבדק לאחרונה: {0}".format(report.run_date)
            if report.run_date
            else u"אין תאריך בדיקה"
        )
        self.source_note_text.Text = self._source_note(report)

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

    def _show_empty(self, message):
        self.empty_hint.Text = message
        self.empty_hint.Visibility = Windows.Visibility.Visible

    # --- NAVIGATION -----------------------------------------------------------

    def _add_nav_button(self, sheet, items):
        button = Windows.Controls.Button()
        button.Content = self._nav_content(sheet, items)
        button.Margin = Windows.Thickness(0, 0, 0, 3)
        button.Padding = Windows.Thickness(8, 5, 8, 5)
        button.HorizontalContentAlignment = Windows.HorizontalAlignment.Stretch
        button.Background = Windows.Media.Brushes.Transparent
        button.BorderBrush = Windows.Media.Brushes.LightGray
        button.Cursor = Windows.Input.Cursors.Hand
        button.MaxWidth = NAV_BUTTON_MAX_WIDTH
        button.ToolTip = self._nav_tooltip(sheet, items)
        # Tag carries the page once built, so MainFrame_Navigated can tell which
        # button to highlight without a parallel lookup table.
        button.Tag = None
        button.Click += self._make_nav_handler(sheet, items, button)

        self.nav_panel.Children.Add(button)
        self._nav_buttons.append((button, self._key_of(sheet)))

    def _nav_content(self, sheet, items):
        grid = Windows.Controls.Grid()
        for width, star in ((0, True), (0, False)):
            column = Windows.Controls.ColumnDefinition()
            column.Width = (
                Windows.GridLength(1, Windows.GridUnitType.Star)
                if star
                else Windows.GridLength.Auto
            )
            grid.ColumnDefinitions.Add(column)

        title = Windows.Controls.TextBlock()
        # Number first, then name. The coordinator numbers these sheets himself
        # and quotes the number when he talks about one; the name repeats the
        # storey, which the planner can already see.
        title.Text = _sheet_label(sheet)
        title.TextTrimming = Windows.TextTrimming.CharacterEllipsis
        title.VerticalAlignment = Windows.VerticalAlignment.Center
        Windows.Controls.Grid.SetColumn(title, 0)
        grid.Children.Add(title)

        score = Windows.Controls.TextBlock()
        score.Text = score_text(sheet.score)
        score.FontWeight = Windows.FontWeights.Bold
        score.Foreground = score_brush(sheet.score)
        score.Margin = Windows.Thickness(8, 0, 0, 0)
        score.VerticalAlignment = Windows.VerticalAlignment.Center
        Windows.Controls.Grid.SetColumn(score, 1)
        grid.Children.Add(score)
        return grid

    def _nav_tooltip(self, sheet, items):
        here = len([i for i in items if i.exists])
        return (
            u"{0}\nגיליון {1}\n{2} מבטים, {3} כבר קיימים אצלך\nציון השורה: {4}"
        ).format(
            sheet.name or u"—",
            sheet.number or u"—",
            len(items),
            here,
            score_text(sheet.score),
        )

    def _key_of(self, sheet):
        return sheet.number or sheet.name or u"?"

    def _make_nav_handler(self, sheet, items, button):
        def handler(sender, e):
            self._open_page(sheet, items, button)

        return handler

    def _open_page(self, sheet, items, button):
        key = self._key_of(sheet)
        page = self._pages.get(key)
        if page is None:
            page = VisualInspectionRowPage(self, sheet, items)
            self._pages[key] = page
        button.Tag = page
        self.main_frame.Navigate(page)

    def _restore_or_open_first(self, remembered):
        """Reopen the row the planner was on, else the worst-scoring one.

        Without this a refresh - which every create and sync triggers - would
        throw them back to the top of the list after every single click.
        """
        target = None
        for button, key in self._nav_buttons:
            if key == remembered:
                target = button
                break
        if target is None and self._nav_buttons:
            target = self._nav_buttons[0][0]
        if target is not None:
            target.RaiseEvent(
                Windows.RoutedEventArgs(Windows.Controls.Button.ClickEvent)
            )

    def _active_key(self):
        page = self.main_frame.Content if hasattr(self, "main_frame") else None
        if page is None:
            return None
        for button, key in self._nav_buttons:
            if button.Tag is page:
                return key
        return None

    def main_frame_Navigated(self, sender, e):
        current = self.main_frame.Content
        for button, _key in self._nav_buttons:
            button.Background = (
                ACTIVE_NAV_BACKGROUND
                if button.Tag is not None and button.Tag is current
                else Windows.Media.Brushes.Transparent
            )

    # --- ACTIONS --------------------------------------------------------------

    def queue_many(self, items, sync):
        """Queue create/sync for a set of rows and wake the External Event."""
        actionable = [i for i in items if i.can_create]
        if not actionable:
            self.set_status(mirror.MIRROR_UNSUPPORTED_KIND, GRAY)
            return
        comp_doc = self.comp_doc
        if comp_doc is None:
            self.set_status(read.COMP_LINK_BROKEN_MSG, RED)
            return
        transform = self.comp_link.GetTotalTransform()

        queued = 0
        skipped = []
        for item in actionable:
            entry = {
                "kind": "view",
                "view_id": item.view_id,
                "view_name": item.view_name,
                "sync": bool(sync),
            }
            # A plan needs a level in THIS model, and settling which one can
            # mean asking. That has to happen here, on the UI thread, before
            # anything is queued: the queue is drained inside an open
            # transaction, and putting a dialog in there is how a model ends up
            # half-written while a planner is away from their desk.
            if item.kind == KIND_PLAN:
                level, problem = self._level_for(item, comp_doc, transform)
                if level is None:
                    skipped.append(problem)
                    continue
                entry["level_id"] = RevitUtils.getElementIdValue(self.doc, level.Id)
            self._pending.append(entry)
            queued += 1

        if not queued:
            self.set_status(skipped[0] if skipped else u"אין מה לבצע.", RED)
            return

        message = (
            u"מסנכרן {0} מבטים...".format(queued)
            if sync
            else u"יוצר אצלך {0} מבטים...".format(queued)
        )
        if skipped:
            message = u"{0} ({1} דולגו: {2})".format(
                message, len(skipped), skipped[0]
            )
        self.set_status(message, GRAY)
        self._event.Raise()

    def _level_for(self, item, comp_doc, transform):
        """The planner's level for a comp plan. (level, problem).

        Remembered for the life of the window: a row is a level, so without the
        cache a "create all" over eight plans on the same storey would ask the
        same question eight times.
        """
        comp_view = comp_doc.GetElement(
            RevitUtils.getElementId(comp_doc, item.view_id)
        )
        if comp_view is None:
            return None, u"המבט '{0}' כבר אינו קיים בקומפילציה.".format(
                item.view_name
            )

        level, options, error = mirror.resolve_level(self.doc, comp_view, transform)
        if error:
            return None, u"'{0}': {1}".format(item.view_name, error)
        if level is not None:
            return level, None

        comp_level = comp_view.GenLevel
        key = RevitUtils.getElementIdValue(comp_doc, comp_level.Id)
        if key in self._level_choice:
            chosen = self.doc.GetElement(
                RevitUtils.getElementId(self.doc, self._level_choice[key])
            )
            if chosen is not None:
                return chosen, None

        chosen = self._ask_for_level(comp_level, options)
        if chosen is None:
            return None, u"'{0}': לא נבחרה קומה.".format(item.view_name)
        self._level_choice[key] = RevitUtils.getElementIdValue(self.doc, chosen.Id)
        return chosen, None

    def _ask_for_level(self, comp_level, options):
        """Let the planner pick between levels sitting at the same height."""
        from pyrevit import forms

        by_label = {}
        for level in options:
            by_label[level.Name] = level
        try:
            picked = forms.SelectFromList.show(
                sorted(by_label.keys()),
                title=u"איזו קומה אצלך מקבילה ל-'{0}'?".format(comp_level.Name),
                button_name=u"בחר",
                multiselect=False,
            )
        finally:
            self.take_focus()
        return by_label.get(picked)

    def execute_pending(self, uiapp):
        """Runs on Revit's API context. Drains the whole queue in one go."""
        pending, self._pending = self._pending, []
        if not pending:
            return

        comp_link = self.comp_link
        comp_doc = self.comp_doc
        if comp_doc is None:
            self.set_status(read.COMP_LINK_BROKEN_MSG, RED)
            return
        transform = comp_link.GetTotalTransform()

        done = 0
        notes = []
        failed = []
        transaction = Transaction(self.doc, "pyBpm | Visual Inspection - mirror views")
        transaction.Start()
        try:
            for item in pending:
                if item.get("kind") == "template":
                    ok, message = self._replace_template(item, comp_doc)
                elif item.get("kind") == "delete":
                    ok, message = self._delete_view(item)
                else:
                    ok, message = self._run_one(item, comp_doc, transform)
                if ok:
                    done += 1
                    if message:
                        notes.append(message)
                else:
                    failed.append(message)
            transaction.Commit()
        except Exception:
            if transaction.HasStarted() and not transaction.HasEnded():
                transaction.RollBack()
            raise

        self.reload()
        self._report(done, notes, failed)

    def _report(self, done, notes, failed):
        parts = []
        if done:
            parts.append(u"בוצעו {0} פעולות.".format(done))
        # Deduplicated, because only three notes fit and a whole row's worth of
        # views shares one template: without this, syncing 13 views spends all
        # three slots on three copies of the same template sentence and buries
        # anything that was actually about a view.
        seen = set()
        unique = [n for n in notes if not (n in seen or seen.add(n))]
        parts.extend(unique[:3])
        if len(unique) > 3:
            parts.append(u"(ועוד {0} הערות)".format(len(unique) - 3))
        if failed:
            parts.append(u"נכשלו {0}: {1}".format(len(failed), failed[0]))
        self.set_status(u"  ".join(parts) or u"", RED if failed else GREEN)

    def _run_one(self, item, comp_doc, transform):
        """(succeeded, message) for one queued action. Inside a transaction."""
        comp_view = comp_doc.GetElement(
            RevitUtils.getElementId(comp_doc, item["view_id"])
        )
        if comp_view is None:
            return False, u"המבט '{0}' כבר אינו קיים בקומפילציה.".format(
                item["view_name"]
            )

        # A plan's level was settled on the UI thread, before this queue was
        # raised, precisely so that nothing here has to ask a question inside
        # an open transaction.
        level = None
        if item.get("level_id") is not None:
            level = self.doc.GetElement(
                RevitUtils.getElementId(self.doc, item["level_id"])
            )
            if level is None:
                return False, u"הקומה שנבחרה עבור '{0}' כבר אינה קיימת.".format(
                    item["view_name"]
                )

        view = None
        rebuilt = False
        if item["sync"]:
            view = mirror.find_mirrored_view(self.doc, item["view_name"])
            if view is None:
                # It was there when the list was drawn and is not now. Creating
                # it is what the planner wanted either way.
                item["sync"] = False
            elif level is not None:
                view, rebuilt, error = mirror.resync_plan(
                    self.doc, view, comp_view, transform, level
                )
                if error:
                    return False, error
            else:
                view, rebuilt, error = mirror.resync_section(
                    self.doc, view, comp_view, transform
                )
                if error:
                    return False, error

        if not item["sync"]:
            if level is not None:
                view, error = mirror.mirror_plan(
                    self.doc, comp_view, transform, level
                )
            else:
                view, error = mirror.mirror_section(self.doc, comp_view, transform)
            if error:
                return False, error

        note = self._carry_template(view, comp_view, comp_doc)
        if rebuilt:
            # Not a warning and not a failure - but the planner should hear
            # that the view in front of them is a new one, because anything
            # they had drawn inside the old one went with it.
            reason = (
                u"הקומה של התכנית השתנתה"
                if level is not None
                else u"הכיוון או המישור של החתך בקומפילציה השתנו"
            )
            remade = (
                u"'{0}': {1}, ולכן המבט נוצר מחדש (סימונים שציירת בתוכו לא "
                u"נשמרו)."
            ).format(view.Name, reason)
            note = u"{0} {1}".format(remade, note) if note else remade
        return True, note

    def _carry_template(self, view, comp_view, comp_doc):
        """Give the new view the compilation's graphics. Returns a note or None.

        The whole point of mirroring: a view cut in the right place but drawn
        under different graphics is not the view that was scored. Failure here
        is reported as a NOTE rather than as a failure - the view itself was
        created correctly and is still worth having.
        """
        if view is None:
            return None
        template, differences, error = templates.ensure_template(
            self.doc, comp_doc, comp_view
        )
        if error:
            return u"'{0}': {1}".format(view.Name, error)

        _applied, apply_error = templates.apply_template(view, template)
        if apply_error:
            return u"'{0}': {1}".format(view.Name, apply_error)
        if differences:
            return (
                u"שים לב: ה-View Template '{0}' שאצלך שונה מזה שבקומפילציה "
                u"({1} הבדלים). לחיצה על ⓘ בשורה מציגה במה, ומאפשרת להחליף."
            ).format(template.Name, len(differences))
        return None

    def open_view(self, item):
        """Go to the planner's own copy of this view. No transaction needed."""
        view = mirror.find_mirrored_view(self.doc, item.view_name)
        if view is None:
            self.set_status(
                u"המבט '{0}' אינו קיים אצלך — יש ליצור אותו קודם.".format(
                    item.view_name
                ),
                RED,
            )
            return
        try:
            self.uidoc.ActiveView = view
            self.set_status(u"עברת למבט '{0}'.".format(view.Name), GREEN)
        except Exception as ex:
            self.set_status(u"לא ניתן לפתוח את המבט: {0}".format(ex), RED)

    def ask(self, message, title, options=None):
        """forms.alert, with the dashboard given the focus back afterwards.

        EVERY dialog this window raises goes through here, and that is the
        whole point of it existing. A modal dialog takes the foreground and
        does not hand it back to a MODELESS window when it closes: the
        dashboard drops behind the Revit window and the planner has to go
        hunting for it after every confirmation. Doing the re-activation in one
        place - in a finally, so it also happens when the dialog is dismissed
        or throws - is what stops it being re-forgotten at the next dialog
        someone adds.
        """
        from pyrevit import forms

        try:
            return forms.alert(message, title=title, options=options)
        finally:
            self.take_focus()

    def take_focus(self):
        """Bring the dashboard back in front. Never worth failing a click over."""
        try:
            self.Activate()
            self.Focus()
        except Exception:
            pass

    def delete_view(self, item):
        """Delete the planner's own copy of a view, after saying what goes.

        The warning is not a formality. The view is the planner's - they may
        have dimensioned or annotated it since it was mirrored - and none of
        that is recoverable from the compilation, which only knows where the
        cut was. So the dialog names what is about to be lost rather than
        asking "are you sure".
        """
        view = mirror.find_mirrored_view(self.doc, item.view_name)
        if view is None:
            self.set_status(
                u"המבט '{0}' כבר אינו קיים אצלך.".format(item.view_name), GRAY
            )
            return

        # Revit refuses to delete the view you are standing in, and the switch
        # away cannot happen inside the transaction that does the deleting -
        # so this is caught here, where it can still be said plainly.
        try:
            if self.uidoc.ActiveView.Id == view.Id:
                self.set_status(
                    u"'{0}' הוא המבט הפתוח כרגע ואי אפשר למחוק מבט פעיל. "
                    u"עבור למבט אחר ונסה שוב.".format(view.Name),
                    RED,
                )
                return
        except Exception:
            pass

        sheet = mirror.sheet_placed_on(self.doc, view)
        warning = (
            u"למחוק את המבט '{0}' מהמודל שלך?\n\n"
            u"כל מה שציירת בתוך המבט — מידות, הערות וסימונים — יימחק יחד "
            u"איתו.".format(view.Name)
        )
        if sheet:
            warning += u"\nהמבט מונח על גיליון {0}, וגם ה-Viewport שם יוסר.".format(
                sheet
            )
        warning += (
            u"\n\nהמבט בקומפילציה אינו מושפע, ותמיד אפשר ליצור אותו כאן מחדש "
            u"בלחיצה על 'צור אצלי'. אם התחרטת מיד — Ctrl+Z מחזיר."
        )

        delete = u"מחק את המבט"
        if self.ask(warning, u"מחיקת מבט", [delete, u"ביטול"]) != delete:
            return

        self._pending.append(
            {
                "kind": "delete",
                "view_id": item.view_id,
                "view_name": item.view_name,
            }
        )
        self.set_status(u"מוחק את '{0}'...".format(item.view_name), GRAY)
        self._event.Raise()

    def _delete_view(self, item):
        """(succeeded, message) for one queued deletion. Inside a transaction."""
        view = mirror.find_mirrored_view(self.doc, item["view_name"])
        if view is None:
            return False, u"המבט '{0}' כבר אינו קיים אצלך.".format(
                item["view_name"]
            )
        name = view.Name
        try:
            self.doc.Delete(view.Id)
        except Exception as ex:
            return False, u"לא ניתן למחוק את '{0}': {1}".format(name, ex)
        return True, u"המבט '{0}' נמחק מהמודל שלך.".format(name)

    def show_template_differences(self, item):
        """Spell out how the local template differs, and offer to fix it.

        The dialog reads the model to count the views that would come along.
        That is a read, which is legal from a modeless window; the replacement
        itself is a write and goes through the External Event like everything
        else.
        """
        if not item.template_differences:
            self.set_status(u"אין הבדלים ב-View Template.", GREEN)
            return
        name = item.template_name
        local = templates.find_template_by_name(self.doc, name)
        followers = len(templates.views_using(self.doc, local))

        replace = u"החלף את התבנית שלי בזו של הקומפילציה"
        answer = self.ask(
            u"ההבדלים בין ה-View Template '{0}' שאצלך לזה שבמודל הקומפילציה:"
            u"\n\n".format(name)
            + u"\n".join(u"• " + d for d in item.template_differences)
            + u"\n\nהחלפה תביא את התבנית מהקומפילציה במקום שלך, תחת אותו שם. "
            u"{0} מבטים במודל שלך נמצאים כרגע על התבנית הזו ויעברו יחד איתה — "
            u"גם כאלה שאינם קשורים לבדיקה הויזואלית.".format(followers),
            u"View Template",
            [replace, u"סגור"],
        )
        if answer != replace:
            return

        self._pending.append(
            {
                "kind": "template",
                "view_id": item.view_id,
                "view_name": item.view_name,
                "template_name": name,
            }
        )
        self.set_status(u"מחליף את ה-View Template '{0}'...".format(name), GRAY)
        self._event.Raise()

    def _replace_template(self, item, comp_doc):
        """(succeeded, message) for one queued replacement. In a transaction."""
        comp_view = comp_doc.GetElement(
            RevitUtils.getElementId(comp_doc, item["view_id"])
        )
        if comp_view is None:
            return False, u"המבט '{0}' כבר אינו קיים בקומפילציה.".format(
                item["view_name"]
            )

        template, moved, remaining, error = templates.replace_template(
            self.doc, comp_doc, comp_view
        )
        if error:
            return False, error

        message = (
            u"ה-View Template '{0}' הוחלף בזה של הקומפילציה, ו-{1} מבטים "
            u"אצלך עברו אליו."
        ).format(template.Name, moved)
        reason = templates.remaining_reason(remaining)
        if reason:
            message = u"{0} {1}".format(message, reason)
        return True, message

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


class _LooseGroup(object):
    """Views that carry a score but sit on no sheet.

    Not an error - a coordinator may create views before building the sheets -
    but they would otherwise have no page to live on and would vanish from the
    dashboard entirely.
    """

    def __init__(self, views):
        self.number = None
        self.name = u"מבטים שאינם על גיליון"
        self.run_date = None
        scored = [v.score for v in views if v.score is not None]
        self.score = min(scored) if scored else None
        self.views = views
