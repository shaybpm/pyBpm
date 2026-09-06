# -*- coding: utf-8 -*-
"""One inspection row - a sheet and its views - as a page in the dashboard.

The window owns the compilation link, the External Event and every write; this
page owns only the presentation of one row and hands actions back up. That
split is what lets a page be rebuilt cheaply on every refresh without touching
the event plumbing.

Rows bind to plain IronPython objects (ViewRowItem) rather than to a WPF
collection type - the pattern used across the extension. WPF reads the
attributes straight off them, so a change to an attribute needs the grid's
ItemsSource re-set rather than a property-changed notification; the page is
cheap to rebuild, so it is rebuilt.

Worst score first. The dashboard exists to find gaps, and a list that opens on
what already passes makes a planner scroll past their own good news.
"""

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

import os
import sys

from pyrevit.framework import wpf
from System import Windows

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))

import VisualInspectionMirror as mirror  # type: ignore
import VisualInspectionRead as read  # type: ignore
import VisualInspectionTemplate as templates  # type: ignore


xaml_file = os.path.join(os.path.dirname(__file__), "VisualInspectionRowPage.xaml")

# Where a score stops being a warning and starts being a problem. Deliberately
# coarse: the number is a similarity measure, not a grade, and pretending to
# finer resolution than that would be false precision.
SCORE_BAD = 60.0
SCORE_GOOD = 85.0

KIND_SECTION = u"חתך"
KIND_PLAN = u"תכנית"
MIRRORABLE_KINDS = (KIND_SECTION, KIND_PLAN)

TEMPLATE_LABELS = {
    templates.STATE_NONE: u"—",
    templates.STATE_MISSING: u"תועתק",
    templates.STATE_SAME: u"זהה",
    templates.STATE_DIFFERS: u"שונה!",
}


def score_tier(score):
    if score is None:
        return "none"
    if score < SCORE_BAD:
        return "red"
    if score < SCORE_GOOD:
        return "orange"
    return "green"


def score_text(score):
    if score is None:
        return u"—"
    return u"{0:.0f}".format(score)


def score_brush(score):
    if score is None:
        return Windows.Media.Brushes.Gray
    if score < SCORE_BAD:
        return Windows.Media.Brushes.Firebrick
    if score < SCORE_GOOD:
        return Windows.Media.Brushes.DarkOrange
    return Windows.Media.Brushes.SeaGreen


class ViewRowItem(object):
    """One inspection view, as the grid shows it.

    Holds the view's ElementId in the COMPILATION model, never the view - the
    page outlives the read that produced it, and a link reload would rot a live
    handle (see the revit-element-lifetime rule).
    """

    def __init__(self, entry, exists, template_state, template_differences,
                 template_name=None):
        self.view_id = entry.view_id
        self.view_name = entry.name or u""
        self.kind = entry.kind or u""
        self.grid_name = _grid_of(entry.name)
        self.detail_number = entry.detail_number or u"—"
        self.score = entry.score
        self.score_text = score_text(entry.score)
        # Unscored sorts last rather than first: a missing score is not the
        # worst score, it is no score.
        self.score_sort = 999.0 if entry.score is None else float(entry.score)
        self.tier = score_tier(entry.score)

        self.exists = bool(exists)
        self.exists_text = u"כן" if exists else u"לא"

        self.template_state = template_state
        self.template_differences = template_differences or []
        self.template_name = template_name
        self.template_text = TEMPLATE_LABELS.get(template_state, u"—")

        self.can_create = self.kind in MIRRORABLE_KINDS
        if self.kind == KIND_SECTION:
            self.create_tooltip = (
                u"יוצר את המבט הזה במודל שלך, במקום המדויק שבו הוא נחתך "
                u"בקומפילציה, ומחיל עליו את ה-View Template של הקומפילציה "
                u"(מעתיק אותו אם אינו קיים אצלך)."
            )
            self.sync_tooltip = (
                u"מחזיר את המבט שלך למיקום, לחיתוך ולעומק שיש לו כרגע "
                u"בקומפילציה. הגיאומטריה שלך נדרסת; שם המבט לא משתנה. "
                u"אם החתך בקומפילציה הועבר למישור אחר או סובב — המבט ייווצר "
                u"מחדש, וסימונים שציירת בתוכו לא יישמרו."
            )
        elif self.kind == KIND_PLAN:
            # The level is worth naming in both tooltips. It is the one thing
            # about a plan that this tool cannot read off the compilation - it
            # has to find the planner's own level at the same HEIGHT, since
            # level names need not agree between two models - and so it is the
            # one thing the planner may be asked about.
            self.create_tooltip = (
                u"יוצר את התכנית הזו במודל שלך: מאתר אצלך את הקומה שבאותו "
                u"גובה כמו בקומפילציה, מעתיק את גבהי החיתוך ואת מסגרת החיתוך, "
                u"ומחיל את ה-View Template של הקומפילציה. אם יש אצלך יותר "
                u"מקומה אחת באותו גובה — תישאל באיזו לבחור."
            )
            self.sync_tooltip = (
                u"מחזיר את התכנית שלך לגבהי החיתוך ולמסגרת שיש לה כרגע "
                u"בקומפילציה. שם המבט לא משתנה, והמבט עצמו נשמר — תכנית "
                u"נוצרת מחדש רק אם הקומה שהותאמה לה השתנתה."
            )
        else:
            self.create_tooltip = mirror.MIRROR_UNSUPPORTED_KIND
            self.sync_tooltip = mirror.MIRROR_UNSUPPORTED_KIND

        self.template_info_visibility = (
            Windows.Visibility.Visible
            if template_state == templates.STATE_DIFFERS
            else Windows.Visibility.Collapsed
        )


def _grid_of(view_name):
    """The grid axis out of a Visual Inspection view name, for its own column.

    Two conventions, because two are in the models. Since 2026-09 DEV.tab names
    a section "V_<level>_<scope box>_<axis>", so the axis is the last segment
    and a plan is recognised by ending in the view type instead. Before that it
    was "BPM_VI__<level>__<scope box>__SEC__<axis>", where the word SEC marks
    which name has an axis at all.

    Best effort either way: a view the planner renamed simply shows nothing
    here, which is better than showing a guess. Only names carrying the tool's
    own prefix are read at all - a planner's own "V_something" is left alone.
    """
    if not view_name:
        return u""
    if view_name.startswith(read.LEGACY_VIEW_NAME_PREFIX):
        parts = view_name.split(u"__")
        if len(parts) >= 2 and parts[-2] == u"SEC":
            return parts[-1]
        return u""
    if view_name.startswith(read.VIEW_NAME_PREFIX):
        parts = view_name.split(u"_")
        # "V", the level, and at least one more segment - anything shorter has
        # no room for an axis. A plan ends in its view type, not in an axis.
        if len(parts) >= 3 and parts[-1] not in read.VIEW_TYPE_NAMES:
            return parts[-1]
    return u""


class VisualInspectionRowPage(Windows.Controls.Page):
    def __init__(self, window, sheet, items):
        wpf.LoadComponent(self, xaml_file)
        self.window = window
        self.sheet = sheet
        self.items = items
        self._render()

    # --- rendering ------------------------------------------------------------

    def _render(self):
        self.row_score_text.Text = score_text(self.sheet.score)
        self.row_score_text.Foreground = score_brush(self.sheet.score)
        self.row_title_text.Text = self.sheet.name or self.sheet.number or u"—"
        self.row_subtitle_text.Text = self._subtitle()

        self.views_grid.ItemsSource = None
        self.views_grid.ItemsSource = self.items

        missing = [i for i in self.items if i.can_create and not i.exists]
        present = [i for i in self.items if i.can_create and i.exists]
        self.create_all_btn.IsEnabled = bool(missing)
        self.sync_all_btn.IsEnabled = bool(present)
        self.create_all_btn.Content = u"צור אצלי הכל ({0})".format(len(missing))
        self.sync_all_btn.Content = u"סנכרן הכל ({0})".format(len(present))

        self._render_template_note()

    def _subtitle(self):
        parts = []
        if self.sheet.number:
            parts.append(u"גיליון {0}".format(self.sheet.number))
        parts.append(u"{0} מבטים".format(len(self.items)))
        if self.sheet.run_date:
            parts.append(u"נבדק {0}".format(self.sheet.run_date))
        return u"  ·  ".join(parts)

    def _render_template_note(self):
        """One line above the grid when any template here disagrees.

        Worth a banner rather than only a column: a template that differs means
        the drawing in front of the planner is not the drawing that was scored,
        which quietly invalidates the comparison they are about to make.
        """
        differing = [i for i in self.items
                     if i.template_state == templates.STATE_DIFFERS]
        if not differing:
            self.template_note.Visibility = Windows.Visibility.Collapsed
            return
        self.template_note.Visibility = Windows.Visibility.Visible
        self.template_note.Foreground = Windows.Media.Brushes.DarkOrange
        self.template_note.Text = (
            u"ל-{0} מבטים בשורה הזו ה-View Template שאצלך שונה מזה שבקומפילציה. "
            u"המבט אצלך ייראה אחרת מזה שקיבל את הציון. לחיצה על ⓘ בשורה מציגה "
            u"בדיוק במה, ומאפשרת להחליף את התבנית שלך בזו של "
            u"הקומפילציה.".format(len(differing))
        )

    # --- events ---------------------------------------------------------------

    def CreateAll_Click(self, sender, e):
        self.window.queue_many(
            [i for i in self.items if i.can_create and not i.exists], sync=False
        )

    def SyncAll_Click(self, sender, e):
        self.window.queue_many(
            [i for i in self.items if i.can_create and i.exists], sync=True
        )

    def Create_Click(self, sender, e):
        self.window.queue_many([sender.DataContext], sync=False)

    def Sync_Click(self, sender, e):
        self.window.queue_many([sender.DataContext], sync=True)

    def Open_Click(self, sender, e):
        self.window.open_view(sender.DataContext)

    def Delete_Click(self, sender, e):
        # Straight to the window, not queued here: it warns first, and the
        # warning needs the model (is this view on a sheet? is it the one open
        # right now?), which the page has no business reaching into.
        self.window.delete_view(sender.DataContext)

    def TemplateInfo_Click(self, sender, e):
        self.window.show_template_differences(sender.DataContext)
