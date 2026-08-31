# -*- coding: utf-8 -*-
"""Mirror an inspection view from the compilation model into the planner's own.

The dashboard tells a planner which axis of which floor scored badly. That is
only half an answer: to fix it they need to be LOOKING at that axis, in their
own model, cut exactly where the coordinator cut it. So the view is rebuilt
here - same plane, same crop, same depth - out of the comp view's geometry
transformed through the link.

The geometry is taken from the comp section's CROP REGION rather than from its
bounding box: the crop is what the coordinator actually framed and what the
score was computed from, and a section's bounding box is not the same rectangle.
The maths is the proven one from GetBpmSections' SectionsCreate, which does the
same job for coordination sections; what differs here is the naming and the
fact that an already-mirrored view is offered a re-sync instead of a duplicate.

Plans are not mirrored yet - see MIRROR_UNSUPPORTED_PLAN. A section is fixed in
space by three vectors that the comp view hands over directly; a plan would
have to be matched to a LEVEL in the planner's model, and level names do not
have to agree between models.

IronPython 2.7. None of these functions open a transaction - the caller does.
"""

from Autodesk.Revit.DB import (
    BoundingBoxXYZ,
    BuiltInCategory,
    BuiltInParameter,
    ElementId,
    ElementTypeGroup,
    FilteredElementCollector,
    Transform,
    View,
    ViewFamilyType,
    ViewSection,
    XYZ,
)

import RevitUtils  # extension-level lib


MIRROR_UNSUPPORTED_PLAN = (
    u"יצירה של תכנית במודל שלך עדיין לא נתמכת — רק חתכים."
)
MIRROR_NO_SECTION_TYPE = u"לא נמצא סוג מבט (ViewFamilyType) של חתך במודל שלך."
MIRROR_NO_CROP = (
    u"למבט בקומפילציה אין אזור חיתוך (Crop Region) שאפשר להעתיק ממנו."
)
RESYNC_ON_SHEET = (
    u"החתך בקומפילציה עבר למישור אחר או סובב, ולכן אי אפשר לסנכרן אותו "
    u"בעריכה — צריך ליצור אותו מחדש, והמבט שלך מונח על גיליון. הסר אותו "
    u"מהגיליון ולחץ סנכרן שוב, או השאר אותו כמות שהוא."
)

# How far the planner's cutting plane may sit from the compilation's and still
# count as the same plane. A hair over nothing: when the two agree the measured
# difference is exactly 0.0 (verified live), so this only absorbs the rounding
# of a round trip through the link transform.
PLANE_TOLERANCE = 1e-3  # feet


# --- IS IT ALREADY HERE? ------------------------------------------------------


def find_mirrored_view(doc, comp_view_name):
    """The planner-side copy of a comp view, by name. None when not mirrored.

    Named identically to the comp view on purpose. The name already carries the
    BPM_VI prefix, the level, the scope box and the grid, so it is unique
    enough to be an identity, and a planner comparing the two models side by
    side sees the same string in both Project Browsers.
    """
    if not comp_view_name:
        return None
    for view in FilteredElementCollector(doc).OfClass(View).ToElements():
        try:
            if view.IsTemplate:
                continue
            if view.Name == comp_view_name:
                return view
        except Exception:
            continue
    return None


def mirrored_names(doc):
    """Every view name in the planner's model, for a fast "exists" column."""
    names = set()
    for view in FilteredElementCollector(doc).OfClass(View).ToElements():
        try:
            if not view.IsTemplate:
                names.add(view.Name)
        except Exception:
            continue
    return names


# --- CREATING -----------------------------------------------------------------


def section_type_id(doc):
    """The model's default section type, or any section type it has."""
    default_id = doc.GetDefaultElementTypeId(ElementTypeGroup.ViewTypeSection)
    if default_id is not None and default_id != ElementId.InvalidElementId:
        return default_id

    for view_family_type in (
        FilteredElementCollector(doc).OfClass(ViewFamilyType).ToElements()
    ):
        try:
            if view_family_type.FamilyName == "Section":
                return view_family_type.Id
        except Exception:
            continue
    return None


def mirror_section(doc, comp_view, transform):
    """Create the planner-side twin of a comp section. Returns (view, error).

    Must run inside a transaction opened by the caller.
    """
    if not isinstance(comp_view, ViewSection):
        return None, MIRROR_UNSUPPORTED_PLAN

    view_family_type_id = section_type_id(doc)
    if view_family_type_id is None:
        return None, MIRROR_NO_SECTION_TYPE

    section_box, error = _section_box_from(comp_view, transform)
    if section_box is None:
        return None, error

    view = ViewSection.CreateSection(doc, view_family_type_id, section_box)
    view.Name = _free_name(doc, comp_view.Name)
    return view, None


def resync_section(doc, view, comp_view, transform):
    """Put an existing mirrored section back onto the comp view's geometry.

    Returns (view, rebuilt, error) - the view being the one to carry on with,
    which is NOT necessarily the one passed in.

    Two thirds of a section can be edited and one third cannot, and the whole
    shape of this function follows from that (all three measured against a live
    model, none of it inferred):

      - the crop rectangle and the far clip are editable, so an in-plane move
        or a resize is done in place;
      - the view's DIRECTION is fixed at creation;
      - so is its cutting PLANE. Revit clamps a crop box to the plane the view
        already has, and ElementTransformUtils.MoveElement on a ViewSection
        returns success while doing nothing at all.

    A comp view that was re-cut in a different direction or at a different
    plane therefore cannot be followed by editing - the view is deleted and
    remade under the same name. That loses anything drawn inside it, so the
    caller is told it happened (`rebuilt`), and a view sitting on a sheet is
    refused rather than pulled out from under its viewport.
    """
    if not isinstance(view, ViewSection) or not isinstance(comp_view, ViewSection):
        return None, False, MIRROR_UNSUPPORTED_PLAN

    section_box, error = _section_box_from(comp_view, transform)
    if section_box is None:
        return None, False, error

    if _crop_can_reach(view, section_box):
        low, high = _in_view_frame(view, section_box)
        _apply_crop(view, low, high)
        return view, False, None

    if _placed_on_sheet(doc, view):
        return view, False, RESYNC_ON_SHEET

    name = view.Name
    try:
        doc.Delete(view.Id)
    except Exception as ex:
        return None, False, u"לא ניתן למחוק את המבט הישן: {0}".format(ex)

    rebuilt, error = mirror_section(doc, comp_view, transform)
    if rebuilt is None:
        return None, False, error
    rebuilt.Name = _free_name(doc, name)
    return rebuilt, True, None


def _crop_can_reach(view, section_box):
    """Can this view be edited into the target, or must it be remade?

    Editable means: it already looks the same way, and its cutting plane is
    already the target's. Everything else about the frame - where the rectangle
    sits in the plane, how big it is, how deep it cuts - the crop can express.
    """
    if not _same_orientation(view, section_box):
        return False
    try:
        current_near = view.CropBox.Min.Z
    except Exception:
        return False
    low, _high = _in_view_frame(view, section_box)
    return abs(low.Z - current_near) <= PLANE_TOLERANCE


def _in_view_frame(view, section_box):
    """The target box's extent, re-expressed in the view's OWN crop frame.

    This is the whole trick behind editing a crop. Assigning a BoundingBoxXYZ
    to View.CropBox does NOT place it by its own Transform - Revit ignores that
    and reads Min/Max in the frame the view already has, so a box handed over
    in world terms lands somewhere else entirely (measured: 39 ft off). Mapping
    the eight corners through the inverse of the view's frame and taking their
    extent says the same thing in the language the setter actually speaks.
    """
    inverse = view.CropBox.Transform.Inverse
    points = []
    for x in (section_box.Min.X, section_box.Max.X):
        for y in (section_box.Min.Y, section_box.Max.Y):
            for z in (section_box.Min.Z, section_box.Max.Z):
                points.append(
                    inverse.OfPoint(section_box.Transform.OfPoint(XYZ(x, y, z)))
                )
    low = XYZ(
        min(p.X for p in points), min(p.Y for p in points), min(p.Z for p in points)
    )
    high = XYZ(
        max(p.X for p in points), max(p.Y for p in points), max(p.Z for p in points)
    )
    return low, high


def _apply_crop(view, low, high):
    """Write an already-translated extent onto the view. Needs a transaction."""
    new_box = BoundingBoxXYZ()
    new_box.Enabled = True
    new_box.Transform = view.CropBox.Transform
    new_box.Min = low
    new_box.Max = high

    view.CropBoxActive = True
    view.CropBox = new_box
    try:
        far = view.get_Parameter(BuiltInParameter.VIEWER_BOUND_OFFSET_FAR)
        if far is not None and not far.IsReadOnly:
            far.Set(high.Z - low.Z)
    except Exception:
        pass


def _placed_on_sheet(doc, view):
    """Is this view sitting in a viewport somewhere? Then it is not ours to delete."""
    for viewport in (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Viewports)
        .WhereElementIsNotElementType()
    ):
        try:
            if viewport.ViewId == view.Id:
                return True
        except Exception:
            continue
    return False


# --- THE GEOMETRY -------------------------------------------------------------


def _section_box_from(comp_view, transform):
    """The comp section's crop, in the planner's coordinates. (box, error)."""
    corners = _crop_corners(comp_view)
    if corners is None:
        return None, MIRROR_NO_CROP

    # Two conventions meet here, and the negation converts between them rather
    # than turning the view around: Revit's View.ViewDirection points FROM the
    # model TOWARDS the viewer, while a section box's BasisZ points the way the
    # view looks. Negating Z means the twin looks the same way as the original,
    # which is the whole point; BasisX follows so the frame stays right-handed.
    # Verified: the mirrored view reports the same ViewDirection and
    # RightDirection as the comp view, and its crop lands on the same point.
    view_direction = -1 * transform.OfVector(comp_view.ViewDirection)
    up_direction = transform.OfVector(comp_view.UpDirection)
    right_direction = -1 * transform.OfVector(comp_view.RightDirection)

    corners = [transform.OfPoint(point) for point in corners]

    height = None
    length = None
    for i in range(len(corners)):
        following = corners[(i + 1) % len(corners)]
        edge = following - corners[i]
        if height is None and abs(edge.DotProduct(right_direction)) < 1e-9:
            height = edge.GetLength()
        if length is None and abs(edge.DotProduct(up_direction)) < 1e-9:
            length = edge.GetLength()
    if not height or not length:
        return None, MIRROR_NO_CROP

    try:
        far_clip = comp_view.get_Parameter(
            BuiltInParameter.VIEWER_BOUND_OFFSET_FAR
        ).AsDouble()
    except Exception:
        far_clip = 0.0
    if far_clip <= 0:
        # A zero-depth section is not a legal view. The inspection sections are
        # a thin slice by design, so a small default is closer to the truth
        # than anything generous.
        far_clip = 0.5

    centre = XYZ(0, 0, 0)
    for point in corners:
        centre = centre + point
    centre = centre / len(corners)
    centre = centre + 0.5 * far_clip * view_direction

    frame = Transform.Identity
    frame.Origin = centre
    frame.BasisZ = view_direction
    frame.BasisY = up_direction
    frame.BasisX = right_direction

    section_box = BoundingBoxXYZ()
    section_box.Enabled = True
    section_box.Transform = frame
    section_box.Min = XYZ(-0.5 * length, -0.5 * height, -0.5 * far_clip)
    section_box.Max = XYZ(0.5 * length, 0.5 * height, 0.5 * far_clip)
    return section_box, None


def _crop_corners(comp_view):
    """The four corners of the comp view's crop region, in link coordinates."""
    try:
        shapes = comp_view.GetCropRegionShapeManager().GetCropShape()
    except Exception:
        return None
    if not shapes:
        return None

    iterator = shapes[0].GetCurveLoopIterator()
    corners = []
    while iterator.MoveNext():
        try:
            corners.append(iterator.Current.GetEndPoint(0))
        except Exception:
            return None
    if len(corners) < 4:
        return None
    return corners[:4]


def _same_orientation(view, section_box):
    """Does this view already look the way the comp view does?

    Note the negation, and note that it is not cosmetic. A section box's BasisZ
    is the direction handed to CreateSection, and the view that comes back
    reports the OPPOSITE as its ViewDirection - Revit's two conventions, the
    same pair already reconciled in _section_box_from. Comparing the two
    directly, as this did until it was measured, is therefore False for every
    view in existence, including one this tool created a second earlier: the
    planner clicked "sync" on a fresh view and was told it was cut the wrong
    way. Up is compared too, so a rectangle rotated in its own plane is rebuilt
    rather than approximated by a bounding box.
    """
    try:
        return view.ViewDirection.IsAlmostEqualTo(
            -1 * section_box.Transform.BasisZ
        ) and view.UpDirection.IsAlmostEqualTo(section_box.Transform.BasisY)
    except Exception:
        return False


def _free_name(doc, base_name):
    """base_name, suffixed until nothing in the model answers to it."""
    taken = mirrored_names(doc)
    if base_name not in taken:
        return base_name
    index = 1
    while True:
        index += 1
        candidate = u"{0}_{1}".format(base_name, index)
        if candidate not in taken:
            return candidate
