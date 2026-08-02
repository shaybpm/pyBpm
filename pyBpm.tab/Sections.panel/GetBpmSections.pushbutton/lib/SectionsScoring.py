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
  - Both sides are restricted to elements RUNNING ALONG the view direction
    (SecReport's isVerticalToView rule, T-0291 follow-up): a linear element cut
    lengthwise by the section is neither a reference nor a candidate; elements
    with no linear direction (fittings, equipment, flex) are always eligible.
  - Section score = sum over N reference systems of overlap_i * (100 / N).
  - Every BooleanOperationsUtils call is wrapped in try/except; a system whose
    op fails has unknown overlap -> its contribution is the interval
    [0, 100/N], so the section score is reported as a range (section 5.4).
  - FALLBACK (T-0291): before giving up on a failed boolean op, the overlap is
    ESTIMATED from the two elements' cross-sections in the section view plane -
    center (location-curve/plane intersection, the AddComponents approach) +
    size incl. insulation, as axis-aligned rectangles in view coordinates.
    An estimated system contributes a point value (marked "estimated" for the
    UI) instead of an unknown range; only a system that cannot be estimated
    either still shows as "?".

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
    SolidUtils,
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

import math

import RevitUtils

# Slim fixed depth of the section slab, in feet (matches SecReport.get_view_solid).
VIEW_SOLID_OFFSET = 0.3

# Tolerance for "on the cut plane" depth tests (feet). The visible slab spans
# [-VIEW_SOLID_OFFSET, 0] along the view direction (a section shows what is
# BEHIND the cut plane only).
_DEPTH_EPS = 0.01

# Color tiers on the (lower-bound) score (section 5.5, tightened R2 #3).
TIER_GREEN_MIN = 97
TIER_ORANGE_MIN = 70

# Only elements that RUN ALONG the section's view direction participate in
# scoring (the SecReport isVerticalToView rule) - an element cut lengthwise by
# the section is neither a reference system nor a matching candidate. Radians,
# matches SecReport's tolerance.
DIRECTION_TOLERANCE = 0.1

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


def _get_view_crop_loop(view):
    """The view's crop-region CurveLoop (on the cut plane), or None."""
    try:
        crop_manager = view.GetCropRegionShapeManager()
        if not crop_manager:
            return None
        crop_shape = crop_manager.GetCropShape()
        if not crop_shape or len(crop_shape) == 0:
            return None
        return crop_shape[0]
    except:
        return None


def _build_view_solid(section, transform):
    """Solid slab of what the section actually cuts: the crop-region loop
    extruded VIEW_SOLID_OFFSET BEHIND the cut plane, expressed in the host
    coordinate space. Exact for any section orientation (a rotated section's
    slab is NOT axis-aligned - the old bbox approach ballooned there and let
    elements the section only shows in deep projection count as references).
    Falls back to the legacy axis-aligned box when the exact extrusion cannot
    be built. Returns None if there is no crop region at all."""
    crop_loop = _get_view_crop_loop(section)
    if crop_loop is not None:
        try:
            solid = GeometryCreationUtilities.CreateExtrusionGeometry(
                List[CurveLoop]([crop_loop]),
                section.ViewDirection.Negate(),
                VIEW_SOLID_OFFSET,
            )
            if transform is not None:
                solid = SolidUtils.CreateTransformed(solid, transform)
            if solid is not None and solid.Volume > 0:
                return solid
        except:
            pass

    # Legacy fallback: axis-aligned box over the crop corners (+ depth).
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


# --------------------------------------------------------------------------
# Location + size fallback (T-0291)
#
# When a boolean op fails, the overlap of the failed pair is estimated from
# the two elements' cross-sections in the section view plane: center point
# (location-curve/plane intersection, like the DEV AddComponents tool) and
# size incl. insulation, modeled as axis-aligned rectangles in view coords.
# The fraction of the reference rectangle covered by the planner rectangle
# stands in for the volumetric overlap fraction, so identical centers with
# different sizes do NOT yield a false 100.
# --------------------------------------------------------------------------

# Insulation categories that ENLARGE the outer cross-section. Linings are
# excluded on purpose - they sit inside the duct and do not change its size.
_SIZE_INSULATION_CATEGORY_NAMES = [
    "OST_DuctInsulations",
    "OST_PipeInsulations",
    "OST_DuctCurvesInsulation",
    "OST_PipeCurvesInsulation",
    "OST_PipeFittingInsulation",
    "OST_DuctFittingInsulation",
]

_size_insulation_bics_cache = None


def _size_insulation_bics():
    global _size_insulation_bics_cache
    if _size_insulation_bics_cache is not None:
        return _size_insulation_bics_cache
    bics = []
    for name in _SIZE_INSULATION_CATEGORY_NAMES:
        bic = getattr(BuiltInCategory, name, None)
        if bic is not None:
            bics.append(bic)
    _size_insulation_bics_cache = bics
    return bics


def _try_get(obj, attr):
    """getattr that also swallows .NET property exceptions (e.g. MEPCurve.Diameter
    raises on a rectangular profile instead of returning null)."""
    try:
        return getattr(obj, attr, None)
    except:
        return None


def _is_along_view_direction(element, view_normal, transform=None):
    """SecReport's isVerticalToView rule: an element with a LINEAR location
    curve must run parallel to the view direction (within DIRECTION_TOLERANCE)
    to participate in scoring. Elements with no linear direction (fittings,
    accessories, equipment, flex runs) are always eligible - same spirit as
    SecReport's MechanicalEquipment exemption.

    view_normal must be in the same coordinate space as the element's curve
    (comp side: the section's own ViewDirection, no transform; host side: the
    comp ViewDirection transformed to host + transform=None)."""
    location = _try_get(element, "Location")
    curve = _try_get(location, "Curve") if location is not None else None
    if curve is None:
        return True
    direction = _try_get(curve, "Direction")
    if direction is None:
        return True  # non-linear curve (flex) - no single direction to test
    if transform is not None:
        direction = transform.OfVector(direction)
    angle = view_normal.AngleTo(direction)
    return min(angle, math.pi - angle) <= DIRECTION_TOLERANCE


def _insulation_thickness(element):
    """Thickest insulation dependent of the element, in feet (0.0 if none)."""
    bics = _size_insulation_bics()
    if not bics:
        return 0.0
    try:
        multi = ElementMulticategoryFilter(List[BuiltInCategory](bics))
        dependent_ids = element.GetDependentElements(multi)
    except:
        return 0.0
    doc = element.Document
    thickness = 0.0
    for dep_id in dependent_ids:
        ins_el = doc.GetElement(dep_id)
        if ins_el is None:
            continue
        t = _try_get(ins_el, "Thickness")
        if t and t > thickness:
            thickness = t
    return thickness


def _element_size(element):
    """(width, height) of the element's cross-section in feet, or None when the
    element has no recognizable size (fittings, families)."""
    d = _try_get(element, "Diameter")
    if d:
        return d, d
    w = _try_get(element, "Width")
    h = _try_get(element, "Height")
    if w and h:
        return w, h
    for bip_name in ("RBS_PIPE_OUTER_DIAMETER", "RBS_PIPE_DIAMETER_PARAM"):
        bip = getattr(BuiltInParameter, bip_name, None)
        if bip is None:
            continue
        try:
            param = element.get_Parameter(bip)
            if param:
                value = param.AsDouble()
                if value:
                    return value, value
        except:
            continue
    return None


def _view_plane_in_host(section, transform):
    """(origin, right, up, normal) of the section cut plane, in host coords."""
    origin = section.Origin
    right = section.RightDirection
    up = section.UpDirection
    normal = section.ViewDirection
    if transform is not None:
        origin = transform.OfPoint(origin)
        right = transform.OfVector(right)
        up = transform.OfVector(up)
        normal = transform.OfVector(normal)
    return origin, right.Normalize(), up.Normalize(), normal.Normalize()


def _bbox_rect_on_plane(element, transform, origin, right, up, normal):
    """Rectangle (cx, cy, half_w, half_h) of the element's bounding box projected
    onto the view plane axes (all 8 corners, so rotation-safe). None when there
    is no bbox or the bbox does not reach the section slab (depth guard)."""
    bbox = element.get_BoundingBox(None)
    if bbox is None:
        return None
    bt = bbox.Transform
    us, vs, ws = [], [], []
    for x in (bbox.Min.X, bbox.Max.X):
        for y in (bbox.Min.Y, bbox.Max.Y):
            for z in (bbox.Min.Z, bbox.Max.Z):
                p = bt.OfPoint(XYZ(x, y, z))
                if transform is not None:
                    p = transform.OfPoint(p)
                d = p.Subtract(origin)
                us.append(d.DotProduct(right))
                vs.append(d.DotProduct(up))
                ws.append(d.DotProduct(normal))
    # The visible slab is BEHIND the cut plane: [-VIEW_SOLID_OFFSET, 0].
    if min(ws) > _DEPTH_EPS or max(ws) < -VIEW_SOLID_OFFSET - _DEPTH_EPS:
        return None  # entirely outside the section slab
    min_u, max_u = min(us), max(us)
    min_v, max_v = min(vs), max(vs)
    return (
        (min_u + max_u) / 2.0,
        (min_v + max_v) / 2.0,
        (max_u - min_u) / 2.0,
        (max_v - min_v) / 2.0,
    )


def _cross_section_rect(element, transform, origin, right, up, normal):
    """Estimated cross-section rectangle (cx, cy, half_w, half_h) of the element
    in the section view plane, or None.

    Preferred: location-curve/plane intersection for the center + size params
    incl. insulation (exact center, exact size - the AddComponents approach).
    Fallback: projected bounding box + insulation. Rectangle axes are assumed
    aligned with the view axes (true for runs cut across by the section)."""
    ins = _insulation_thickness(element)
    location = _try_get(element, "Location")
    curve = _try_get(location, "Curve") if location is not None else None
    if curve is not None:
        size = _element_size(element)
        if size is not None:
            try:
                p0 = curve.GetEndPoint(0)
                p1 = curve.GetEndPoint(1)
                if transform is not None:
                    p0 = transform.OfPoint(p0)
                    p1 = transform.OfPoint(p1)
                d0 = normal.DotProduct(p0.Subtract(origin))
                d1 = normal.DotProduct(p1.Subtract(origin))
                center = None
                if (d0 > 0) != (d1 > 0):
                    t = d0 / (d0 - d1)
                    center = p0.Add(p1.Subtract(p0).Multiply(t))
                else:
                    # No crossing - use an end that terminates inside the
                    # visible slab ([-VIEW_SOLID_OFFSET, 0]), if any, projected
                    # onto the cut plane.
                    in_slab = [
                        (p, d)
                        for (p, d) in ((p0, d0), (p1, d1))
                        if -VIEW_SOLID_OFFSET - _DEPTH_EPS <= d <= _DEPTH_EPS
                    ]
                    if in_slab:
                        end, dist = min(in_slab, key=lambda pair: abs(pair[1]))
                        center = end.Subtract(normal.Multiply(dist))
                if center is not None:
                    d = center.Subtract(origin)
                    return (
                        d.DotProduct(right),
                        d.DotProduct(up),
                        size[0] / 2.0 + ins,
                        size[1] / 2.0 + ins,
                    )
            except:
                pass
    rect = _bbox_rect_on_plane(element, transform, origin, right, up, normal)
    if rect is None:
        return None
    return (rect[0], rect[1], rect[2] + ins, rect[3] + ins)


def _rect_overlap_fraction(ref_rect, other_rect):
    """Fraction [0..1] of ref_rect's area covered by other_rect."""
    ref_cx, ref_cy, ref_hw, ref_hh = ref_rect
    o_cx, o_cy, o_hw, o_hh = other_rect
    ref_area = 4.0 * ref_hw * ref_hh
    if ref_area <= 0:
        return 0.0
    overlap_w = min(ref_cx + ref_hw, o_cx + o_hw) - max(ref_cx - ref_hw, o_cx - o_hw)
    overlap_h = min(ref_cy + ref_hh, o_cy + o_hh) - max(ref_cy - ref_hh, o_cy - o_hh)
    if overlap_w <= 0 or overlap_h <= 0:
        return 0.0
    fraction = (overlap_w * overlap_h) / ref_area
    return 1.0 if fraction > 1.0 else fraction


def _estimate_pair_fraction(comp_el, comp_transform, mep_el, section):
    """T-0291 fallback for a failed (reference, planner) boolean op: fraction of
    the reference cross-section covered by the planner cross-section. None when
    the estimate is impossible - the caller falls back to unknown ("?")."""
    try:
        origin, right, up, normal = _view_plane_in_host(section, comp_transform)
        ref_rect = _cross_section_rect(
            comp_el, comp_transform, origin, right, up, normal
        )
        if ref_rect is None:
            return None
        other_rect = _cross_section_rect(mep_el, None, origin, right, up, normal)
        if other_rect is None:
            return None
        return _rect_overlap_fraction(ref_rect, other_rect)
    except:
        return None


def _estimate_system_fraction(host_doc, comp_el, comp_transform, section, raw_solid):
    """T-0291 fallback for a reference system whose view-solid clip failed:
    estimate the covered fraction purely from cross-sections (no boolean ops -
    this system already proved boolean-fragile). Candidates are same-category
    planner elements whose bbox meets the comp element's solid bbox; overlaps
    are summed and capped at 1 (same double-count caveat as the volumetric
    path). Returns a fraction in [0..1], or None."""
    try:
        bic = _b_i_category_from_other_doc(host_doc, comp_el.Category)
    except:
        return None
    if bic is None or bic == BuiltInCategory.INVALID:
        return None
    try:
        origin, right, up, normal = _view_plane_in_host(section, comp_transform)
        ref_rect = _cross_section_rect(
            comp_el, comp_transform, origin, right, up, normal
        )
        if ref_rect is None:
            return None
        solid_bbox = raw_solid.GetBoundingBox()
        outline = RevitUtils.getOutlineByBoundingBox(solid_bbox)
        bbox_filter = LogicalOrFilter(
            BoundingBoxIsInsideFilter(outline), BoundingBoxIntersectsFilter(outline)
        )
        candidates = (
            FilteredElementCollector(host_doc)
            .WhereElementIsNotElementType()
            .WherePasses(ElementCategoryFilter(bic))
            .WherePasses(bbox_filter)
            .ToElements()
        )
        total = 0.0
        for mep_el in candidates:
            if not _is_along_view_direction(mep_el, normal):
                continue
            other_rect = _cross_section_rect(mep_el, None, origin, right, up, normal)
            if other_rect is None:
                continue
            total += _rect_overlap_fraction(ref_rect, other_rect)
            if total >= 1.0:
                return 1.0
        return total
    except:
        return None


def _measure_overlap(host_doc, comp_el, comp_clipped, comp_transform, section):
    """Accumulate the volume of comp_clipped occupied by same-category planner
    geometry (insulation included). Returns (intersected_volume, op_failed,
    estimated_used).

    A failed pair boolean op is first estimated from cross-sections (T-0291);
    only when that estimate is also impossible does op_failed come back True -
    the caller then treats this system's overlap as unknown (section 5.4).
    estimated_used is True when at least one pair contribution is estimated."""
    comp_vol = comp_clipped.Volume

    bic = None
    try:
        bic = _b_i_category_from_other_doc(host_doc, comp_el.Category)
    except:
        bic = None
    if bic is None or bic == BuiltInCategory.INVALID:
        # Cannot establish the category -> no same-category match possible.
        return 0.0, False, False

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

    host_view_dir = comp_transform.OfVector(section.ViewDirection).Normalize()

    intersected = 0.0
    estimated_used = False
    for mep_el in candidates:
        if not _is_along_view_direction(mep_el, host_view_dir):
            continue
        mep_solid = _safe_solid(mep_el)
        if mep_solid is None or mep_solid.Volume == 0:
            continue
        mep_solid = _union_insulation(mep_el, mep_solid, None)
        try:
            inter = BooleanOperationsUtils.ExecuteBooleanOperation(
                comp_clipped, mep_solid, BooleanOperationsType.Intersect
            )
        except:
            # T-0291: estimate just this failed pair instead of giving up on the
            # whole system (we know exactly which two elements failed).
            est = _estimate_pair_fraction(comp_el, comp_transform, mep_el, section)
            if est is None:
                return 0.0, True, False
            intersected += est * comp_vol
            estimated_used = True
            if intersected >= comp_vol:
                intersected = comp_vol
                break
            continue
        if inter is not None and inter.Volume > 0:
            intersected += inter.Volume
        if intersected >= comp_vol:
            intersected = comp_vol
            break
    return intersected, False, estimated_used


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

    # Pass 1 - establish the reference systems (and N). An element cut
    # lengthwise by the section (not running along the view direction) is not
    # a reference system - the SecReport rule.
    comp_view_dir = section.ViewDirection
    references = []
    for comp_el in comp_elements:
        if not _is_along_view_direction(comp_el, comp_view_dir):
            continue
        raw = _safe_solid(comp_el, comp_transform)
        if raw is None or raw.Volume == 0:
            continue
        raw = _union_insulation(comp_el, raw, comp_transform)
        clipped, clip_failed = _clip(raw, view_solid)
        if clip_failed:
            # raw is kept for the T-0291 fallback (candidate search by its bbox).
            references.append(
                {"el": comp_el, "clipped": None, "raw": raw, "failed": True}
            )
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
    # system is first estimated from cross-sections (T-0291, "estimated") and
    # only when that is impossible has unknown overlap -> overlap/points are
    # None (section 5.4).
    lower = 0.0
    upper = 0.0
    failed_systems = 0
    estimated_systems = 0
    systems = []
    for ref in references:
        el = ref["el"]
        sys_id = RevitUtils.getElementIdValue(comp_doc, el.Id)
        category = _category_name(el)
        if ref["failed"]:
            # T-0291: view-solid clip failed - estimate the whole system.
            est = _estimate_system_fraction(
                host_doc, el, comp_transform, section, ref["raw"]
            )
            if est is None:
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
                estimated_systems += 1
                lower += est * per_system
                upper += est * per_system
                systems.append({
                    "id": sys_id,
                    "category": category,
                    "overlap": float(est),
                    "points": float(est * per_system),
                    "failed": False,
                    "estimated": True,
                })
            continue
        comp_clipped = ref["clipped"]
        comp_vol = comp_clipped.Volume
        intersected, op_failed, est_used = _measure_overlap(
            host_doc, el, comp_clipped, comp_transform, section
        )
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
            if est_used:
                estimated_systems += 1
            lower += fraction * per_system
            upper += fraction * per_system
            systems.append({
                "id": sys_id,
                "category": category,
                "overlap": float(fraction),
                "points": float(fraction * per_system),
                "failed": False,
                "estimated": bool(est_used),
            })

    return {
        "section_name": RevitUtils.getElementName(section),
        "section_id": RevitUtils.getElementIdValue(comp_doc, section.Id),
        "lower": lower,
        "upper": upper,
        "n": n,
        "failed": failed_systems,
        "estimated": estimated_systems,
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
    # T-0291: a score that includes estimated (fallback) systems is a point
    # value, but flagged as approximate.
    prefix = u"≈" if result.get("estimated") else u""
    if abs(hi - lo) < 0.5:
        return prefix + u"{:.0f}".format(lo)
    return prefix + u"{:.0f}-{:.0f}".format(lo, hi)


def score_tier(lower_bound):
    if lower_bound >= TIER_GREEN_MIN:
        return "green"
    if lower_bound >= TIER_ORANGE_MIN:
        return "orange"
    return "red"
