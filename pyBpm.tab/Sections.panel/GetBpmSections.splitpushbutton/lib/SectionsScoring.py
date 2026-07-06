# -*- coding: utf-8 -*-
""" Volume-match scoring engine for Get Bpm Sections (Phase 2).

Direction (decision #1, reversed vs the internal SecReport tool):
  - REFERENCE = the coordinator's systems inside the section region of the
    compilation model, restricted to the planner's selected discipline filters.
  - TARGET    = the planner's own current-model geometry.
  - Per reference element (a "system", decision R2-4):
        overlap = Vol( Intersect(comp_solid+ins, mep_solid+ins) )
                  / Vol( comp_solid+ins )                       (capped at 1.0)
    matched only against the planner's SAME-category elements (R3 #1).
  - Section score = sum over N reference systems of overlap_i * (100 / N).
  - Every BooleanOperationsUtils call is wrapped in try/except; a system whose
    op fails has unknown overlap -> its contribution is the interval
    [0, 100/N], so the section score is reported as a range (section 5.4).

Everything is computed in the HOST (planner) coordinate space: comp solids are
transformed by the comp link's total transform; the section view solid (built
from the comp-side crop region) is transformed the same way; planner solids are
native. Geometry helpers that the pyBpm RevitUtils lacks are ported here from
the DEV.extension RevitUtils (the SecReport source). IronPython 2.7. """

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    View,
    ViewType,
    BuiltInParameter,
    BuiltInCategory,
    XYZ,
    Line,
    Curve,
    CurveLoop,
    GeometryCreationUtilities,
    BooleanOperationsUtils,
    BooleanOperationsType,
    ElementCategoryFilter,
    ElementMulticategoryFilter,
    ElementIntersectsSolidFilter,
    BoundingBoxIsInsideFilter,
    BoundingBoxIntersectsFilter,
    LogicalOrFilter,
    LogicalAndFilter,
    ElementFilter,
)
from System.Collections.Generic import List

import RevitUtils

# Slim fixed depth of the section slab, in feet (matches SecReport.get_view_solid).
VIEW_SOLID_OFFSET = 0.3

# Color tiers on the (lower-bound) score (section 5.5, tightened R2 #3).
TIER_GREEN_MIN = 97
TIER_ORANGE_MIN = 70

# Insulation + lining categories (decision #4 / R2-note-b). Guarded by getattr so
# a name that does not exist in the running Revit version is simply skipped.
_INSULATION_CATEGORY_NAMES = [
    "OST_DuctInsulations",
    "OST_PipeInsulations",
    "OST_DuctLinings",
    "OST_DuctCurvesInsulation",
    "OST_PipeCurvesInsulation",
    "OST_PipeFittingInsulation",
    "OST_DuctFittingInsulation",
]

_insulation_bics_cache = None


# --------------------------------------------------------------------------
# Ported geometry helpers (not present in pyBpm RevitUtils)
# --------------------------------------------------------------------------
def _get_view_crop_region_corners(view):
    crop_manager = view.GetCropRegionShapeManager()
    if not crop_manager:
        return None, None, None, None
    crop_shape = crop_manager.GetCropShape()
    if not crop_shape or len(crop_shape) == 0:
        return None, None, None, None
    it = crop_shape[0].GetCurveLoopIterator()
    it.MoveNext()
    p1 = it.Current.GetEndPoint(0)
    it.MoveNext()
    p2 = it.Current.GetEndPoint(0)
    it.MoveNext()
    p3 = it.Current.GetEndPoint(0)
    it.MoveNext()
    p4 = it.Current.GetEndPoint(0)
    return p1, p2, p3, p4


def _get_min_max_from_points(points):
    min_x = min(p.X for p in points)
    min_y = min(p.Y for p in points)
    min_z = min(p.Z for p in points)
    max_x = max(p.X for p in points)
    max_y = max(p.Y for p in points)
    max_z = max(p.Z for p in points)
    return XYZ(min_x, min_y, min_z), XYZ(max_x, max_y, max_z)


def _create_solid_cube_by_minmax(min_p, max_p):
    p1 = min_p
    p2 = XYZ(max_p.X, min_p.Y, min_p.Z)
    p3 = XYZ(max_p.X, max_p.Y, min_p.Z)
    p4 = XYZ(min_p.X, max_p.Y, min_p.Z)
    curves = [
        Line.CreateBound(p1, p2),
        Line.CreateBound(p2, p3),
        Line.CreateBound(p3, p4),
        Line.CreateBound(p4, p1),
    ]
    curve_loop = CurveLoop.Create(List[Curve](curves))
    height = max_p.Z - min_p.Z
    return GeometryCreationUtilities.CreateExtrusionGeometry(
        List[CurveLoop]([curve_loop]), XYZ.BasisZ, height
    )


def _category_name(element):
    """Best-effort category display name of an element ("" if unavailable)."""
    try:
        cat = element.Category
        if cat is None:
            return u""
        return cat.Name
    except:
        return u""


def _b_i_category_from_other_doc(host_doc, category):
    if category is None:
        return None
    if RevitUtils.getRevitVersion(host_doc) >= 2023:
        return category.BuiltInCategory
    return BuiltInCategory(RevitUtils.getElementIdValue(host_doc, category.Id))


def _insulation_bics():
    global _insulation_bics_cache
    if _insulation_bics_cache is not None:
        return _insulation_bics_cache
    bics = []
    for name in _INSULATION_CATEGORY_NAMES:
        bic = getattr(BuiltInCategory, name, None)
        if bic is not None:
            bics.append(bic)
    _insulation_bics_cache = bics
    return bics


# --------------------------------------------------------------------------
# Solids (with insulation) and clipping
# --------------------------------------------------------------------------
def _safe_solid(element, transform=None):
    """get_solid_from_element wrapped so a bad element (get_Geometry returns None
    or raises) yields None instead of aborting the whole run."""
    try:
        return RevitUtils.get_solid_from_element(element, transform)
    except:
        return None


def _union_insulation(element, base_solid, transform):
    """Union the element's insulation/lining solids into base_solid (best effort).

    element and its dependents live in element.Document; transform brings the
    solids into the host coordinate space (comp side) or is None (planner side).
    A failed union is skipped rather than aborting the whole element.
    """
    bics = _insulation_bics()
    if not bics:
        return base_solid
    try:
        multi = ElementMulticategoryFilter(List[BuiltInCategory](bics))
        dependent_ids = element.GetDependentElements(multi)
    except:
        return base_solid

    doc = element.Document
    combined = base_solid
    for dep_id in dependent_ids:
        ins_el = doc.GetElement(dep_id)
        if ins_el is None:
            continue
        ins_solid = _safe_solid(ins_el, transform)
        if ins_solid is None or ins_solid.Volume == 0:
            continue
        try:
            combined = BooleanOperationsUtils.ExecuteBooleanOperation(
                combined, ins_solid, BooleanOperationsType.Union
            )
        except:
            continue
    return combined


def _build_view_solid(section, transform):
    """Axis-aligned solid slab bounding the section crop region (+ VIEW_SOLID_OFFSET
    depth), expressed in the host coordinate space. Returns None if it can't be
    built (no crop region / degenerate geometry)."""
    p1, p2, p3, p4 = _get_view_crop_region_corners(section)
    if p1 is None:
        return None
    view_dir = section.ViewDirection
    back = view_dir.Multiply(-VIEW_SOLID_OFFSET)
    points = []
    for p in (p1, p2, p3, p4):
        points.append(p)
        points.append(p.Add(back))
    if transform is not None:
        points = [transform.OfPoint(p) for p in points]
    min_p, max_p = _get_min_max_from_points(points)
    try:
        return _create_solid_cube_by_minmax(min_p, max_p)
    except:
        return None


def _clip(solid, view_solid):
    """Intersect a solid with the section view solid. Returns (clipped, failed)."""
    try:
        result = BooleanOperationsUtils.ExecuteBooleanOperation(
            solid, view_solid, BooleanOperationsType.Intersect
        )
        return result, False
    except:
        return None, True


def _measure_overlap(host_doc, comp_el, comp_clipped):
    """Accumulate the volume of comp_clipped occupied by same-category planner
    geometry (insulation included). Returns (intersected_volume, op_failed).

    op_failed is True if any overlap boolean op raised - the caller then treats
    this system's overlap as unknown (section 5.4)."""
    comp_vol = comp_clipped.Volume

    bic = None
    try:
        bic = _b_i_category_from_other_doc(host_doc, comp_el.Category)
    except:
        bic = None
    if bic is None or bic == BuiltInCategory.INVALID:
        # Cannot establish the category -> no same-category match possible.
        return 0.0, False

    solid_bbox = comp_clipped.GetBoundingBox()
    outline = RevitUtils.getOutlineByBoundingBox(solid_bbox)
    bbox_filter = LogicalOrFilter(
        BoundingBoxIsInsideFilter(outline), BoundingBoxIntersectsFilter(outline)
    )
    solid_filter = ElementIntersectsSolidFilter(comp_clipped)

    candidates = (
        FilteredElementCollector(host_doc)
        .WhereElementIsNotElementType()
        .WherePasses(ElementCategoryFilter(bic))
        .WherePasses(bbox_filter)
        .WherePasses(solid_filter)
        .ToElements()
    )

    intersected = 0.0
    for mep_el in candidates:
        mep_solid = _safe_solid(mep_el)
        if mep_solid is None or mep_solid.Volume == 0:
            continue
        mep_solid = _union_insulation(mep_el, mep_solid, None)
        try:
            inter = BooleanOperationsUtils.ExecuteBooleanOperation(
                comp_clipped, mep_solid, BooleanOperationsType.Intersect
            )
        except:
            return 0.0, True
        if inter is not None and inter.Volume > 0:
            intersected += inter.Volume
        if intersected >= comp_vol:
            intersected = comp_vol
            break
    return intersected, False


# --------------------------------------------------------------------------
# Section collection (is_su_sec logic, from the current pushbutton) + scoring
# --------------------------------------------------------------------------
def _is_su_sec(view, ex_suction_names):
    if not view.ViewType == ViewType.Section:
        return False
    if "SU" not in view.Name:
        return False
    sheet_param = view.get_Parameter(BuiltInParameter.VIEWPORT_SHEET_NUMBER)
    on_sheet = sheet_param is not None and sheet_param.AsString()
    if not on_sheet and view.Name.replace("SU", "EX") not in ex_suction_names:
        return False
    return True


def collect_candidate_sections(comp_doc):
    """Return the comp model's SU section views eligible for scoring (on a sheet,
    or whose EX twin is on a sheet)."""
    all_sections = [
        v
        for v in FilteredElementCollector(comp_doc).OfClass(View).ToElements()
        if v.ViewType == ViewType.Section
    ]
    ex_suction_names = []
    for v in all_sections:
        if "EX" not in v.Name:
            continue
        sheet_param = v.get_Parameter(BuiltInParameter.VIEWPORT_SHEET_NUMBER)
        if sheet_param is not None and sheet_param.AsString():
            ex_suction_names.append(v.Name)
    return [v for v in all_sections if _is_su_sec(v, ex_suction_names)]


def _section_sheet_number(section, views_by_name):
    """The section's effective sheet number: its own VIEWPORT_SHEET_NUMBER, or its
    EX twin's (section 4.6). None if neither is on a sheet."""
    sheet_param = section.get_Parameter(BuiltInParameter.VIEWPORT_SHEET_NUMBER)
    if sheet_param is not None and sheet_param.AsString():
        return sheet_param.AsString()
    ex_name = section.Name.replace("SU", "EX")
    ex_view = views_by_name.get(ex_name)
    if ex_view is not None:
        ex_param = ex_view.get_Parameter(BuiltInParameter.VIEWPORT_SHEET_NUMBER)
        if ex_param is not None and ex_param.AsString():
            return ex_param.AsString()
    return None


def get_candidate_sections_with_sheets(comp_doc):
    """Return (items, sheets): items = [{'section', 'sheet'}] for every candidate
    SU section, and sheets = the sorted unique sheet numbers present."""
    sections = collect_candidate_sections(comp_doc)
    views_by_name = {}
    for v in FilteredElementCollector(comp_doc).OfClass(View).ToElements():
        views_by_name[v.Name] = v
    items = []
    sheets_set = set()
    for section in sections:
        sheet = _section_sheet_number(section, views_by_name)
        items.append({"section": section, "sheet": sheet})
        if sheet:
            sheets_set.add(sheet)
    return items, sorted(sheets_set)


def section_id_value(comp_doc, section):
    """Integer id of a section (used as the cache key for its score)."""
    return RevitUtils.getElementIdValue(comp_doc, section.Id)


def _parameter_filter_to_element_filter(pfe):
    """Convert a ParameterFilterElement to an ElementFilter covering BOTH its
    categories and its rules.

    ParameterFilterElement.GetElementFilter() returns only the parameter RULES
    and drops the CATEGORIES (and returns null for a categories-only filter), so
    combining the two is required - the same approach as the DEV RevitUtils
    get_element_filter_with_categories helper. No element-id rule conversion is
    needed because we apply the filter inside its OWN document (the comp doc),
    not against linked elements. Returns None if the filter has no categories.
    """
    categories = pfe.GetCategories()
    if not categories or categories.Count == 0:
        return None
    category_filters = List[ElementFilter]()
    for category_id in categories:
        category_filters.Add(ElementCategoryFilter(category_id))
    categories_filter = (
        LogicalOrFilter(category_filters)
        if category_filters.Count > 1
        else category_filters[0]
    )
    try:
        rules_filter = pfe.GetElementFilter()
    except:
        rules_filter = None
    if not rules_filter:
        return categories_filter
    return LogicalAndFilter(categories_filter, rules_filter)


def _combined_element_filter(selected_filters):
    element_filters = []
    for f in selected_filters:
        try:
            ef = _parameter_filter_to_element_filter(f)
        except:
            ef = None
        if ef is not None:
            element_filters.append(ef)
    if not element_filters:
        return None
    if len(element_filters) == 1:
        return element_filters[0]
    return LogicalOrFilter(List[ElementFilter](element_filters))


def score_section(host_doc, comp_link, comp_doc, section, selected_filters):
    """Score a single section. Returns a result dict, or None when the section
    has zero reference systems (empty section -> filtered out, decision #2)."""
    combined_filter = _combined_element_filter(selected_filters)
    if combined_filter is None:
        return None

    comp_transform = comp_link.GetTotalTransform()
    view_solid = _build_view_solid(section, comp_transform)
    if view_solid is None:
        return None

    comp_elements = (
        FilteredElementCollector(comp_doc, section.Id)
        .WhereElementIsNotElementType()
        .WherePasses(combined_filter)
        .ToElements()
    )

    # Pass 1 - establish the reference systems (and N).
    references = []
    for comp_el in comp_elements:
        raw = _safe_solid(comp_el, comp_transform)
        if raw is None or raw.Volume == 0:
            continue
        raw = _union_insulation(comp_el, raw, comp_transform)
        clipped, clip_failed = _clip(raw, view_solid)
        if clip_failed:
            references.append({"el": comp_el, "clipped": None, "failed": True})
        elif clipped is None or clipped.Volume == 0:
            continue  # outside the section slab
        else:
            references.append({"el": comp_el, "clipped": clipped, "failed": False})

    n = len(references)
    if n == 0:
        return None
    per_system = 100.0 / n

    # Pass 2 - score each reference system, collecting a per-system record
    # (S1: id + category + overlap/points) for the details panel. A failed
    # system has unknown overlap -> overlap/points are None (section 5.4).
    lower = 0.0
    upper = 0.0
    failed_systems = 0
    systems = []
    for ref in references:
        el = ref["el"]
        sys_id = RevitUtils.getElementIdValue(comp_doc, el.Id)
        category = _category_name(el)
        if ref["failed"]:
            failed_systems += 1
            upper += per_system  # lower += 0 (overlap unknown)
            systems.append({
                "id": sys_id,
                "category": category,
                "overlap": None,
                "points": None,
                "failed": True,
            })
            continue
        comp_clipped = ref["clipped"]
        comp_vol = comp_clipped.Volume
        intersected, op_failed = _measure_overlap(host_doc, el, comp_clipped)
        if op_failed:
            failed_systems += 1
            upper += per_system  # lower += 0 (overlap unknown)
            systems.append({
                "id": sys_id,
                "category": category,
                "overlap": None,
                "points": None,
                "failed": True,
            })
        else:
            fraction = intersected / comp_vol if comp_vol > 0 else 0.0
            if fraction > 1.0:
                fraction = 1.0
            lower += fraction * per_system
            upper += fraction * per_system
            systems.append({
                "id": sys_id,
                "category": category,
                "overlap": float(fraction),
                "points": float(fraction * per_system),
                "failed": False,
            })

    return {
        "section_name": RevitUtils.getElementName(section),
        "section_id": RevitUtils.getElementIdValue(comp_doc, section.Id),
        "lower": lower,
        "upper": upper,
        "n": n,
        "failed": failed_systems,
        "systems": systems,
    }


def compute_all_scores(
    host_doc, comp_link, comp_doc, selected_filters, sections=None, progress_cb=None
):
    """Score all candidate (or the given) sections. Returns (results, skipped)
    where results is the list of non-empty section score dicts and skipped is the
    count of sections filtered out (empty / no view solid)."""
    if sections is None:
        sections = collect_candidate_sections(comp_doc)
    results = []
    skipped = 0
    total = len(sections)
    for i, section in enumerate(sections):
        if progress_cb is not None:
            progress_cb(i, total, RevitUtils.getElementName(section))
        try:
            result = score_section(
                host_doc, comp_link, comp_doc, section, selected_filters
            )
        except:
            # One bad section must never abort the whole run.
            result = None
        if result is None:
            skipped += 1
        else:
            results.append(result)
    return results, skipped


# --------------------------------------------------------------------------
# Presentation helpers
# --------------------------------------------------------------------------
def format_score(result):
    lo = result["lower"]
    hi = result["upper"]
    if abs(hi - lo) < 0.5:
        return "{:.0f}".format(lo)
    return "{:.0f}-{:.0f}".format(lo, hi)


def score_tier(lower_bound):
    if lower_bound >= TIER_GREEN_MIN:
        return "green"
    if lower_bound >= TIER_ORANGE_MIN:
        return "orange"
    return "red"
