# -*- coding: utf-8 -*-
""" Shared logic for the "Hide Openings Out Of Range" split button.

Both sub-buttons (auto-detect by view range / manual pick) feed a list of
{"discipline": str, "mark": str} dicts into the same per-view filter and apply it
on the active plan view. """

from pyrevit import forms

from Autodesk.Revit.DB import (
    ViewPlan,
    ElementId,
    PlanViewPlane,
    BoundingBoxXYZ,
    XYZ,
    FilteredElementCollector,
    BuiltInCategory,
    BoundingBoxIsInsideFilter,
    FamilyInstance,
    RevitLinkInstance,
    Transaction,
    TransactionGroup,
)
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from Autodesk.Revit.Exceptions import OperationCanceledException

from RevitUtils import (
    getElementName,
    getElementIdValue,
    getOutlineByBoundingBox,
    get_all_link_instances,
)
from RevitUtilsOpenings import (
    opening_names,
    get_opening_element_filter,
    get_opening_discipline_and_number,
    get_specific_openings_filter,
    get_current_openings_data_from_specific_openings_filter,
    create_or_modify_specific_openings_filter,
    get_view_specific_openings_filter_name,
)

ALERT_TITLE = "BPM - הסתרת פתחים מחוץ ל-View Range"

# Effectively-unbounded horizontal half-extent (feet). The band only constrains the
# openings vertically (Z); X/Y are left wide open so every opening fully below the
# view range is caught, regardless of its plan location.
HORIZONTAL_HALF_EXTENT = 1.0e6

# Tolerance (feet) for treating the band as degenerate (view depth == bottom clip).
ELEV_TOLERANCE = 1.0e-6


def alert(msg):
    forms.alert(msg, title=ALERT_TITLE)


# --------------------------------------------------------------------------------
# View validation
# --------------------------------------------------------------------------------


def validate_active_view(doc):
    """Returns (view, None) if the active view is usable, else (None, error_message).
    The view must be a plan view (has a View Range) with no View Template."""
    view = doc.ActiveView

    if not isinstance(view, ViewPlan):
        return (
            None,
            "המבט הנוכחי אינו מתאים - יש להריץ את הכלי על מבט תוכנית בעל View Range.",
        )

    if view.ViewTemplateId != ElementId.InvalidElementId:
        return (
            None,
            "לכלי זה ניתן לעבוד רק על מבט ללא View Template.\n"
            "הסר את ה-View Template מהמבט ונסה שוב.",
        )

    return view, None


# --------------------------------------------------------------------------------
# Auto detection by view range (button: Hide By View Range)
# --------------------------------------------------------------------------------


def get_view_range_elevations(doc, view):
    """Returns a dict of absolute elevations (project elevation + offset) for the
    relevant view-range planes, or None where the plane is not set / unlimited."""
    view_range = view.GetViewRange()

    def plane_elevation(plane):
        level = doc.GetElement(view_range.GetLevelId(plane))
        if level is None:
            return None
        return level.ProjectElevation + view_range.GetOffset(plane)

    return {
        "bottom": plane_elevation(PlanViewPlane.BottomClipPlane),
        "viewDepth": plane_elevation(PlanViewPlane.ViewDepthPlane),
        "underlayBottom": plane_elevation(PlanViewPlane.UnderlayBottom),
    }


def build_band_bounding_box(doc, view):
    """Builds the vertical band bounding box (host coordinates) or returns
    (None, error_message). Top Z = bottom of view range; bottom Z = the lower of
    the view-depth / underlay-bottom planes."""
    elevations = get_view_range_elevations(doc, view)

    top_z = elevations["bottom"]
    if top_z is None:
        return None, "לא ניתן לקרוא את המישור התחתון (Bottom) של ה-View Range."

    lower_candidates = [
        elev
        for elev in (elevations["viewDepth"], elevations["underlayBottom"])
        if elev is not None
    ]
    if not lower_candidates:
        return (
            None,
            "ל-View Range של המבט אין מישור View Depth או Underlay Bottom מוגדר.",
        )
    lower_z = min(lower_candidates)

    if top_z - lower_z < ELEV_TOLERANCE:
        return (
            None,
            "ל-View Range אין אזור מתחת למישור התחתון (עומק המבט מתלכד עם ה-Bottom).\n"
            "אין פתחים מתחת ל-View Range להסתרה.",
        )

    bbox = BoundingBoxXYZ()
    bbox.Min = XYZ(-HORIZONTAL_HALF_EXTENT, -HORIZONTAL_HALF_EXTENT, lower_z)
    bbox.Max = XYZ(HORIZONTAL_HALF_EXTENT, HORIZONTAL_HALF_EXTENT, top_z)
    return bbox, None


def collect_openings_below_range(doc, bbox):
    """Iterates every link in the document, collects the openings whose bounding box
    is fully inside the band, and returns a de-duplicated list of
    {"discipline": str, "mark": str} dicts plus the total element count."""
    openings_data = []
    seen = set()
    found_count = 0

    for link in get_all_link_instances(doc):
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue

        opening_element_filter = get_opening_element_filter(link_doc)
        if not opening_element_filter:
            continue

        # The collector runs in the link's document, so the band (host coordinates)
        # is transformed into link coordinates via the link transform inverse.
        bbox_outline = getOutlineByBoundingBox(bbox, link.GetTotalTransform().Inverse)
        inside_filter = BoundingBoxIsInsideFilter(bbox_outline)

        openings = (
            FilteredElementCollector(link_doc)
            .OfCategory(BuiltInCategory.OST_GenericModel)
            .WherePasses(opening_element_filter)
            .WherePasses(inside_filter)
            .ToElements()
        )

        for opening in openings:
            found_count, _ = _accumulate_opening(
                opening, openings_data, seen, found_count
            )

    return openings_data, found_count


# --------------------------------------------------------------------------------
# Manual pick (button: Hide Picked Openings)
# --------------------------------------------------------------------------------


def is_opening_element(element):
    """True if the element is one of the BPM opening family instances."""
    if not isinstance(element, FamilyInstance):
        return False
    try:
        return getElementName(element.Symbol) in opening_names
    except Exception:
        return False


class CustomISelectionFilter(ISelectionFilter):
    """Selection filter that lets the user pick only opening family instances inside
    linked models. `condition` is a predicate(element) -> bool."""

    def __init__(self, doc, condition):
        self.doc = doc
        self.condition = condition

    def AllowElement(self, element):
        # Allow link instances so the user can hover into the links; for any element
        # passed directly, accept it only if it is an opening.
        if isinstance(element, RevitLinkInstance):
            return True
        try:
            return self.condition(element)
        except Exception:
            return False

    def AllowReference(self, reference, position):
        # Resolve the linked element behind the reference and test it.
        try:
            link_instance = self.doc.GetElement(reference.ElementId)
            if not isinstance(link_instance, RevitLinkInstance):
                return False
            link_doc = link_instance.GetLinkDocument()
            if not link_doc:
                return False
            element = link_doc.GetElement(reference.LinkedElementId)
            if not element:
                return False
            return self.condition(element)
        except Exception:
            return False


def pick_openings(uidoc):
    """Lets the user pick opening elements in linked models. Returns
    (openings_data, found_count), or None if the user cancelled."""
    doc = uidoc.Document
    selection_filter = CustomISelectionFilter(doc, is_opening_element)
    msg = "בחר את הפתחים (במודלים המקושרים) שברצונך להסתיר, ולחץ Finish."

    try:
        references = uidoc.Selection.PickObjects(
            ObjectType.LinkedElement, selection_filter, msg
        )
    except OperationCanceledException:
        return None

    openings_data = []
    seen = set()
    found_count = 0
    for reference in references:
        link_instance = doc.GetElement(reference.ElementId)
        if not link_instance:
            continue
        link_doc = link_instance.GetLinkDocument()
        if not link_doc:
            continue
        element = link_doc.GetElement(reference.LinkedElementId)
        if not element or not is_opening_element(element):
            continue
        found_count, _ = _accumulate_opening(
            element, openings_data, seen, found_count
        )

    return openings_data, found_count


def ask_reset_or_add():
    """Asks whether to reset the view filter or add to it. Returns True (reset),
    False (add), or None if the user cancelled."""
    reset_option = "אתחל את הפילטר (החלף את הפתחים המוסתרים)"
    add_option = "הוסף לפתחים המוסתרים הקיימים"
    selected = forms.alert(
        "כיצד לעדכן את פילטר הפתחים המוסתרים במבט?",
        title=ALERT_TITLE,
        options=[reset_option, add_option],
    )
    if not selected:
        return None
    return selected == reset_option


# --------------------------------------------------------------------------------
# Shared filter update + apply
# --------------------------------------------------------------------------------


def update_and_apply_view_filter(doc, view, openings_data, reset):
    """Rebuilds the per-view openings filter and applies it (hides matches) on the
    view. reset=True replaces the content with openings_data; reset=False merges
    openings_data into the filter's current content. Returns the filter, or None."""
    view_id_value = getElementIdValue(doc, view.Id)
    filter_name = get_view_specific_openings_filter_name(view_id_value)

    if not reset:
        existing_filter = get_specific_openings_filter(doc, filter_name)
        if existing_filter:
            current = (
                get_current_openings_data_from_specific_openings_filter(existing_filter)
                or []
            )
            seen = set((o["discipline"], o["mark"]) for o in current)
            merged = list(current)
            for opening in openings_data:
                key = (opening["discipline"], opening["mark"])
                if key not in seen:
                    seen.add(key)
                    merged.append(opening)
            openings_data = merged

    t_group = TransactionGroup(doc, "pyBpm | Hide Openings Out Of Range")
    t_group.Start()

    specific_filter = create_or_modify_specific_openings_filter(
        doc, openings_data, filter_name=filter_name
    )
    if not specific_filter:
        t_group.RollBack()
        return None

    t = Transaction(doc, "pyBpm | Apply Filter To View")
    t.Start()
    if not view.IsFilterApplied(specific_filter.Id):
        view.AddFilter(specific_filter.Id)
    view.SetFilterVisibility(specific_filter.Id, False)
    t.Commit()

    t_group.Assimilate()
    return specific_filter


# --------------------------------------------------------------------------------
# Internal
# --------------------------------------------------------------------------------


def _accumulate_opening(opening, openings_data, seen, found_count):
    """Extracts discipline/mark from an opening and appends a de-duplicated entry.
    Returns the updated (found_count, openings_data)."""
    discipline, mark = get_opening_discipline_and_number(opening)
    if not discipline or not mark:
        return found_count, openings_data
    found_count += 1
    key = (discipline, mark)
    if key not in seen:
        seen.add(key)
        openings_data.append({"discipline": discipline, "mark": mark})
    return found_count, openings_data
