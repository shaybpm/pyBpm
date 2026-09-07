# -*- coding: utf-8 -*-
"""Read the Arc-Const Visual Inspection results out of the compilation model.

The scores are produced by the coordinator's tool in DEV.tab and stored on the
internal site, which planners' offices cannot reach - pyBpm talks only to the
pyBpm Azure server. So the compilation MODEL is the whole data source here:
the coordinator's run writes each score into the sheets and views themselves,
and this module reads them back out.

Three facts have to be recovered, in falling order of reliability:

  1. BPM_VI_Score / BPM_VI_RunDate on a sheet or a view. Written for a machine
     to read, and the only source that gives a score PER sheet and PER view.
  2. The Visual Inspection REVISION on the sheets, which carries the model
     score in its description. Present in models where the shared parameters
     were never bound, and readable by a human on the drawing itself.
  3. The tool's name prefix (V_, or BPM_VI in older models), which finds
     views that exist but were never scored - a view created and not yet
     run is worth showing as "no score yet" rather than not showing at all.

None of the three is trusted to identify a view on its own. A planner can
rename a view and a coordinator can edit a revision description, so a view
counts as part of the inspection if EITHER its name still carries the prefix OR
it holds a run date. Whether it is a plan or a section is asked of its class,
never of its name.

The constants below are duplicated from DEV.tab rather than shared: the two
extensions ship separately, to different machines, and there is no import path
between them. They are a contract - changing a name in DEV.tab without changing
it here silently empties this dashboard.
"""

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    Revision,
    View,
    ViewPlan,
    ViewSection,
    ViewSheet,
    BuiltInCategory,
    BuiltInParameter,
    ElementCategoryFilter,
    ElementId,
)

import RevitUtils  # extension-level lib


# --- THE CONTRACT WITH DEV.tab ------------------------------------------------

# DEV.tab names a view "V_<level>_<scope box>_<axis>" since 2026-09, and
# "BPM_VI__<level>__<scope box>__<TYPE>__<axis>" before that. Both are still
# in the models, so both are recognised - nothing here ever writes a name.
VIEW_NAME_PREFIX = "V_"
LEGACY_VIEW_NAME_PREFIX = "BPM_VI"
# The SLOT a view fills in its row, as DEV.tab writes it into the name. A view
# with no grid axis ends in its slot code; anything else there is the axis name.
VIEW_TYPE_TOP = "TOP"
VIEW_TYPE_SECTION = "SEC"
# The slab itself, seen from both sides: FLR-TOP is a floor plan, FLR-BOT is a
# Reflected Ceiling Plan. Both cover the same absolute band and differ only in
# which way they look.
VIEW_TYPE_FLOOR_TOP = "FLR-TOP"
VIEW_TYPE_FLOOR_BOTTOM = "FLR-BOT"
VIEW_TYPE_NAMES = (
    VIEW_TYPE_TOP,
    VIEW_TYPE_SECTION,
    VIEW_TYPE_FLOOR_TOP,
    VIEW_TYPE_FLOOR_BOTTOM,
)
# What each slot is called wherever a person reads it. Copied verbatim from
# DEV.tab's _VIEW_TYPE_LABELS, which is the naming authority: the coordinator
# and the planner are looking at the same view and had better call it the same
# thing when they talk about it.
VIEW_TYPE_LABELS = {
    VIEW_TYPE_TOP: u"תכנית",
    VIEW_TYPE_SECTION: u"חתך",
    VIEW_TYPE_FLOOR_TOP: u"רצפה מלמעלה",
    VIEW_TYPE_FLOOR_BOTTOM: u"רצפה מלמטה",
}
PARAM_SCORE = "BPM_VI_Score"
PARAM_RUN_DATE = "BPM_VI_RunDate"
REVISION_PREFIX = u"בדיקה ויזואלית אדריכלות-קונסטרוקציה"


def view_type_of(view_name):
    """The slot a view fills, out of its name. None when the name does not say.

    Two conventions, because two are in the models at once. Since 2026-09 a
    view is "V_<level>_<scope box>_<slot or axis>", so the slot is the last
    segment when it is one of ours. Before that it was
    "BPM_VI__<level>__<scope box>__<SLOT>__<axis>", where the slot is named
    outright and the axis follows it.

    Best effort, and only for names carrying the tool's own prefix: a view the
    planner renamed says nothing about its slot, which is better than guessing.
    """
    if not view_name:
        return None
    if view_name.startswith(LEGACY_VIEW_NAME_PREFIX):
        parts = view_name.split(u"__")
        for candidate in (parts[-1], parts[-2] if len(parts) >= 2 else None):
            if candidate in VIEW_TYPE_NAMES:
                return candidate
        return None
    if view_name.startswith(VIEW_NAME_PREFIX):
        parts = view_name.split(u"_")
        # "V", the level, and at least one more segment - anything shorter has
        # no room for a slot.
        if len(parts) >= 3 and parts[-1] in VIEW_TYPE_NAMES:
            return parts[-1]
    return None


# --- PRECONDITIONS ------------------------------------------------------------

NOT_IN_CLOUD_MSG = u"המודל אינו מודל ענן. הכלי עובד רק על מודלים ב-Autodesk Docs."
COMP_LINK_NOT_LOADED_MSG = (
    u"מודל הקומפילציה אינו טעון בפרויקט. יש לטעון אותו כדי לראות את תוצאות "
    u"הבדיקה הוויזואלית."
)
COMP_LINK_BROKEN_MSG = u"הלינק של מודל הקומפילציה קיים אך אינו טעון (Unloaded)."


def check_preconditions(doc):
    """(comp_link, comp_doc, error). error is None when everything is in place.

    The cloud check comes first because get_comp_link -> get_model_info raises
    on a document that is not in the cloud.
    """
    if not doc.IsModelInCloud:
        return None, None, NOT_IN_CLOUD_MSG

    comp_link = RevitUtils.get_comp_link(doc)
    if not comp_link:
        return None, None, COMP_LINK_NOT_LOADED_MSG

    comp_doc = comp_link.GetLinkDocument()
    if not comp_doc:
        return None, None, COMP_LINK_BROKEN_MSG

    return comp_link, comp_doc, None


# --- WHAT WE READ -------------------------------------------------------------


class ViewEntry(object):
    """One inspected view, as it stands in the compilation model."""

    def __init__(self, view_id, name, kind, detail_number, score, run_date):
        self.view_id = view_id
        self.name = name
        # "תכנית" / "חתך" / "מבט" - from the view's class, not its name.
        self.kind = kind
        self.detail_number = detail_number
        self.score = score
        self.run_date = run_date


class SheetEntry(object):
    """One inspection sheet - a level x scope box row - and its views."""

    def __init__(self, sheet_id, number, name, score, run_date):
        self.sheet_id = sheet_id
        self.number = number
        self.name = name
        self.score = score
        self.run_date = run_date
        self.views = []

    @property
    def worst_view(self):
        scored = [v for v in self.views if v.score is not None]
        if not scored:
            return None
        return min(scored, key=lambda v: v.score)


class InspectionReport(object):
    def __init__(self, model_score, run_date, sheets, loose_views, source):
        self.model_score = model_score
        self.run_date = run_date
        # Sorted worst-first: the dashboard exists so a planner can find the
        # gaps, and a list that opens on the levels already passing makes them
        # scroll past their own good news.
        self.sheets = sheets
        # Inspection views that sit on no sheet. Not an error - a coordinator
        # may create views before building the sheets - but they carry scores
        # and would otherwise be invisible.
        self.loose_views = loose_views
        # "params" or "revision" - which of the two sources the model score
        # came from. Shown, because a model still on the revision fallback has
        # no per-view scores at all and the planner should know why.
        self.source = source

    @property
    def is_empty(self):
        return not self.sheets and not self.loose_views


# --- READING ------------------------------------------------------------------


def read_inspection(comp_doc):
    """Everything the dashboard shows, read out of the compilation model."""
    views_by_sheet_id, loose_views = _collect_views(comp_doc)

    sheets = []
    for sheet in FilteredElementCollector(comp_doc).OfClass(ViewSheet).ToElements():
        sheet_id_int = _id_value(comp_doc, sheet.Id)
        views = views_by_sheet_id.pop(sheet_id_int, [])
        score = _score_of(sheet)
        run_date = _run_date_of(sheet)
        if not views and score is None:
            continue
        entry = SheetEntry(
            sheet_id=sheet_id_int,
            number=_safe(lambda: sheet.SheetNumber),
            name=_safe(lambda: sheet.Name),
            score=score,
            run_date=run_date,
        )
        entry.views = sorted(views, key=_by_score_then_name)
        sheets.append(entry)

    # A sheet id that survived the pop belongs to a sheet the collector did not
    # return - deleted mid-read, or in a workset that is not open.
    for orphaned in views_by_sheet_id.values():
        loose_views.extend(orphaned)

    sheets.sort(key=_by_score_then_name)
    loose_views.sort(key=_by_score_then_name)

    model_score, run_date, source = _model_score(comp_doc, sheets, loose_views)
    return InspectionReport(model_score, run_date, sheets, loose_views, source)


def _collect_views(comp_doc):
    """({sheet id: [ViewEntry]}, [ViewEntry not on any sheet])."""
    by_sheet = {}
    loose = []

    for view in FilteredElementCollector(comp_doc).OfClass(View).ToElements():
        if not _is_inspection_view(view):
            continue

        viewport = _viewport_of(comp_doc, view)
        entry = ViewEntry(
            view_id=_id_value(comp_doc, view.Id),
            name=_safe(lambda: view.Name),
            kind=_kind_of(view),
            detail_number=_detail_number(viewport),
            score=_score_of(view),
            run_date=_run_date_of(view),
        )

        if viewport is None:
            loose.append(entry)
            continue
        sheet_id = _id_value(comp_doc, viewport.OwnerViewId)
        by_sheet.setdefault(sheet_id, []).append(entry)

    return by_sheet, loose


def _is_inspection_view(view):
    """Named by the tool, or carrying a run date. Either is enough.

    Both halves are needed. The name alone misses a view the planner renamed;
    the run date alone misses a view that was created but never scored, which
    is exactly the gap the dashboard should be pointing at.
    """
    try:
        if view.IsTemplate:
            return False
    except Exception:
        return False
    if isinstance(view, ViewSheet):
        return False

    name = _safe(lambda: view.Name) or u""
    if name.startswith(VIEW_NAME_PREFIX) or name.startswith(
        LEGACY_VIEW_NAME_PREFIX
    ):
        return True
    return bool(_run_date_of(view))


def _kind_of(view):
    if isinstance(view, ViewPlan):
        return u"תכנית"
    if isinstance(view, ViewSection):
        return u"חתך"
    return u"מבט"


def _viewport_of(comp_doc, view):
    """The viewport placing this view, or None when it is on no sheet.

    Asked of the API rather than read off VIEWER_SHEET_NUMBER: that parameter
    is text and Revit fills it with "---" for an unplaced view, so it tells you
    whether a view is placed but never which viewport placed it - and the
    viewport is what carries the Detail Number.
    """
    try:
        dependent_ids = view.GetDependentElements(
            ElementCategoryFilter(BuiltInCategory.OST_Viewports)
        )
    except Exception:
        return None

    for dependent_id in dependent_ids:
        dependent = comp_doc.GetElement(dependent_id)
        if dependent is None:
            continue
        try:
            if (
                dependent.OwnerViewId != ElementId.InvalidElementId
                and dependent.ViewId == view.Id
            ):
                return dependent
        except Exception:
            continue
    return None


def _detail_number(viewport):
    if viewport is None:
        return None
    try:
        param = viewport.get_Parameter(BuiltInParameter.VIEWPORT_DETAIL_NUMBER)
        value = param.AsString() if param is not None else None
    except Exception:
        return None
    return value or None


# --- THE VALUES ---------------------------------------------------------------


def _score_of(element):
    """The score, or None when this element was never scored.

    The RUN DATE is what says whether a score exists, not the score parameter
    itself. BPM_VI_Score is a Number, and a Number parameter that was never
    written reads back as 0.0 rather than as empty - so trusting it alone would
    report every unscored sheet as scoring zero, which is the worst score there
    is and exactly the row a planner would rush to. Zero is also a REAL score
    (a level where nothing matches), so it cannot simply be treated as absent
    either; only the date separates the two.
    """
    if not _run_date_of(element):
        return None
    try:
        param = element.LookupParameter(PARAM_SCORE)
        if param is None:
            return None
        return param.AsDouble()
    except Exception:
        return None


def _run_date_of(element):
    try:
        param = element.LookupParameter(PARAM_RUN_DATE)
        if param is None:
            return None
        return param.AsString() or None
    except Exception:
        return None


def _model_score(comp_doc, sheets, loose_views):
    """(score, run date, source) for the model as a whole.

    Preferred from the sheets, because that is what the coordinator's run
    actually wrote. The revision is the fallback for a model where the shared
    parameters were never bound - there the description is the only record.
    """
    scored = [s for s in sheets if s.score is not None]
    if scored:
        # The tool writes the same model score onto every inspection sheet, so
        # any of them answers. The newest run date is taken across all of them
        # so a partially re-run model still reports when it last ran.
        dates = [s.run_date for s in sheets + loose_views if s.run_date]
        return scored[0].score, (max(dates) if dates else None), "params"

    revision = _latest_inspection_revision(comp_doc)
    if revision is None:
        return None, None, None
    return (
        _score_from_description(revision.Description),
        _safe(lambda: revision.RevisionDate),
        "revision",
    )


def _latest_inspection_revision(comp_doc):
    found = []
    for revision in (
        FilteredElementCollector(comp_doc).OfClass(Revision).ToElements()
    ):
        description = _safe(lambda: revision.Description) or u""
        if description.startswith(REVISION_PREFIX):
            found.append(revision)
    if not found:
        return None
    # SequenceNumber orders revisions the way the project itself does; the
    # date is a free-text field and cannot be sorted on.
    return max(found, key=lambda r: _safe(lambda: r.SequenceNumber) or 0)


def _score_from_description(description):
    """Pull the number out of "... - model score 71".

    Read from the END of the text rather than by matching the sentence around
    it: the description is a field a human may edit, and the wording is far
    more likely to change than the fact that it finishes with the number.
    """
    if not description:
        return None
    tail = description.strip().split()
    while tail:
        candidate = tail.pop().strip(u".,;:()[]")
        try:
            return float(candidate)
        except (ValueError, TypeError):
            continue
    return None


# --- SMALL HELPERS ------------------------------------------------------------


def _by_score_then_name(entry):
    """Worst score first; unscored last; then by name, so the order is stable."""
    score = entry.score
    name = getattr(entry, "number", None) or entry.name or u""
    if score is None:
        return (1, 0.0, name)
    return (0, score, name)


def _id_value(doc, element_id):
    try:
        return RevitUtils.getElementIdValue(doc, element_id)
    except Exception:
        try:
            return element_id.IntegerValue
        except Exception:
            return None


def _safe(getter):
    try:
        return getter()
    except Exception:
        return None
