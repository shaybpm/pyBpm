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

SECTIONS AND PLANS are mirrored, and they are mirrored differently because they
are pinned down by different things. A section is fixed in space by three
vectors the comp view hands over directly, so it crosses the link as pure
geometry. A plan is fixed by a LEVEL, a view range measured from levels, and a
scope box - three things that exist as ELEMENTS in the compilation and have no
counterpart in the planner's model. So the plan half of this module is mostly
about translating those: the level is found by ELEVATION rather than by name
(see resolve_level), the view range crosses as absolute elevations, and the
scope box crosses as the crop shape it produces rather than as itself.

IronPython 2.7. None of these functions open a transaction - the caller does.
"""

from Autodesk.Revit.DB import (
    BoundingBoxXYZ,
    BuiltInCategory,
    BuiltInFailures,
    BuiltInParameter,
    CurveLoop,
    ElementId,
    ElementTypeGroup,
    FailureProcessingResult,
    FilteredElementCollector,
    IFailuresPreprocessor,
    Level,
    PlanViewPlane,
    Transform,
    View,
    ViewFamilyType,
    ViewPlan,
    ViewSection,
    XYZ,
)

import RevitUtils  # extension-level lib


MIRROR_UNSUPPORTED_KIND = (
    u"יצירה של מבט מסוג זה במודל שלך אינה נתמכת — רק חתכים ותכניות."
)
MIRROR_NO_SECTION_TYPE = u"לא נמצא סוג מבט (ViewFamilyType) של חתך במודל שלך."
MIRROR_NO_PLAN_TYPE = u"לא נמצא סוג מבט (ViewFamilyType) של תכנית במודל שלך."
# The floor-from-below view is a Reflected Ceiling Plan, and a floor plan type
# cannot stand in for it - plan_type_id never falls back to another family, and
# should not. Saying only "תכנית" would send the planner to check the one thing
# their model certainly does have.
MIRROR_NO_CEILING_TYPE = (
    u"לא נמצא סוג מבט (ViewFamilyType) של תכנית תקרה משתקפת "
    u"(Reflected Ceiling Plan) במודל שלך. המבט הזה מציג את הרצפה מלמטה ולכן "
    u"הוא RCP — סוג מבט של תכנית רגילה לא יוכל להחליף אותו."
)
MIRROR_NO_STRUCTURAL_TYPE = (
    u"לא נמצא סוג מבט (ViewFamilyType) של תכנית קונסטרוקציה "
    u"(Structural Plan) במודל שלך."
)
MIRROR_NO_GEN_LEVEL = u"לתכנית בקומפילציה אין קומה שאפשר להתאים לפיה."
MIRROR_NO_LEVEL_MATCH = (
    u"אין במודל שלך קומה בגובה {0:.2f} מ' — הגובה של הקומה '{1}' בקומפילציה. "
    u"אם המודלים אמורים להיות מתואמים, זה עצמו ממצא."
)
MIRROR_NO_CROP = (
    u"למבט בקומפילציה אין אזור חיתוך (Crop Region) שאפשר להעתיק ממנו."
)
RESYNC_ON_SHEET = (
    u"החתך בקומפילציה עבר למישור אחר או סובב, ולכן אי אפשר לסנכרן אותו "
    u"בעריכה — צריך ליצור אותו מחדש, והמבט שלך מונח על גיליון. הסר אותו "
    u"מהגיליון ולחץ סנכרן שוב, או השאר אותו כמות שהוא."
)
# Not a failure: the view exists and is in the right place, it just did not get
# the compilation's cut depths. Said out loud rather than swallowed, because a
# plan sitting at its type's DEFAULT view range looks perfectly normal and is
# not the view that was scored.
RANGE_NOT_APPLIED = (
    u"'{0}': גבהי החיתוך (View Range) לא הועתקו מהקומפילציה, והמבט נשאר עם "
    u"הטווח שברירת המחדל של סוג המבט נתנה לו. {1}"
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
    tool's prefix, the level, the scope box and the grid, so it is unique
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
        return None, MIRROR_UNSUPPORTED_KIND

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
        return None, False, MIRROR_UNSUPPORTED_KIND

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


def sheet_placed_on(doc, view):
    """The number of the sheet this view sits on, or None if it sits on none.

    The number rather than a yes/no, because everywhere this matters the
    planner is about to be told something about their view and "on sheet A-101"
    is the difference between a warning they can act on and one they cannot.
    """
    for viewport in (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Viewports)
        .WhereElementIsNotElementType()
    ):
        try:
            if viewport.ViewId != view.Id:
                continue
            sheet = doc.GetElement(viewport.SheetId)
            return sheet.SheetNumber if sheet is not None else u"?"
        except Exception:
            continue
    return None


def _placed_on_sheet(doc, view):
    """Is this view in a viewport somewhere? Then it is not ours to delete."""
    return sheet_placed_on(doc, view) is not None


# --- PLANS: FINDING THE LEVEL -------------------------------------------------

# How far apart two levels may sit and still be the same storey. About a
# centimetre: far below any real difference in how two disciplines model a
# floor, far above the rounding of a transform.
LEVEL_TOLERANCE = 1.0 / 32.0  # feet

# A view family to the ElementTypeGroup holding the model's default type for
# it. Keyed by the enum's NAME rather than the enum value: keying a dict by a
# .NET enum through IronPython is one more thing to be sure of for no gain.
_DEFAULT_TYPE_GROUPS = {
    u"FloorPlan": ElementTypeGroup.ViewTypeFloorPlan,
    u"CeilingPlan": ElementTypeGroup.ViewTypeCeilingPlan,
    u"StructuralPlan": ElementTypeGroup.ViewTypeStructuralPlan,
}

PLAN_PLANES = (
    PlanViewPlane.TopClipPlane,
    PlanViewPlane.CutPlane,
    PlanViewPlane.BottomClipPlane,
    PlanViewPlane.ViewDepthPlane,
)


def resolve_level(doc, comp_view, transform):
    """Which of the planner's levels is the comp plan's level? (level, options, error).

    Matched by ELEVATION, never by name. Level names do not have to agree
    between an architect's model and an engineer's - "02AC" against "L02" -
    but elevations do: if the two models disagree about where a floor is they
    are not coordinated, and the inspection that produced this score was
    meaningless. So the one thing that must agree is the one thing matched on.

    Returns exactly one of three things:
      - (level, [], None)      one obvious answer, take it
      - (None, options, None)  several levels at that elevation, ask
      - (None, [], error)      nothing there, and that is worth saying out loud

    Several is not an edge case: a model routinely carries an architectural and
    a structural level at the same height. Guessing between them would put the
    view on the wrong storey silently, which is why it asks.
    """
    comp_level = _gen_level(comp_view)
    if comp_level is None:
        return None, [], MIRROR_NO_GEN_LEVEL

    target = transform.OfPoint(XYZ(0, 0, comp_level.ProjectElevation)).Z
    options = [
        level
        for level in FilteredElementCollector(doc).OfClass(Level).ToElements()
        if abs(level.ProjectElevation - target) <= LEVEL_TOLERANCE
    ]

    if not options:
        return None, [], MIRROR_NO_LEVEL_MATCH.format(
            RevitUtils.convertRevitNumToCm(doc, target) / 100.0,
            _name_of(comp_level),
        )
    if len(options) == 1:
        return options[0], [], None

    preferred = preferred_level(options, _name_of(comp_level))
    if preferred is not None:
        return preferred, [], None
    return None, options, None


def preferred_level(options, comp_name):
    """The one of several same-elevation levels that shares the comp's name.

    Name is useless for FINDING the level and decisive for choosing between
    levels already known to be at the right height - so it is used here and
    only here, to spare the planner a question that has an obvious answer.
    """
    if not comp_name:
        return None
    for level in options:
        if _name_of(level) == comp_name:
            return level
    flattened = u" ".join(comp_name.split()).lower()
    for level in options:
        if u" ".join(_name_of(level).split()).lower() == flattened:
            return level
    return None


def _gen_level(view):
    try:
        return view.GenLevel
    except Exception:
        return None


def _name_of(element):
    try:
        return element.Name or u""
    except Exception:
        return u""


# --- PLANS: CREATING ----------------------------------------------------------


def plan_type_id(doc, comp_view):
    """The type to build the mirrored plan with. None when there is none.

    The model's DEFAULT type of the compilation plan's family, falling back to
    any type of that family. Same shape as section_type_id, deliberately: the
    two paths answer the same question and had no business answering it
    differently.

    Why the default rather than the first one found, which is what this did
    first: view types are not interchangeable containers. This model carries
    six floor plan types and each one auto-applies a DIFFERENT view template to
    new views (02_SC_FLOOR_PLAN_EX brings 02_SC_EX_Plans, 01_AC_FLOOR_PLAN
    brings 01_AC_Plans, and so on). "Whatever the collector yields first" was
    picking 02_SC_FLOOR_PLAN_EX while the model's own default is
    01_AC_FLOOR_PLAN - an arbitrary answer to a question the model already has
    an answer to, and collector order is not promised to be stable anyway.

    The family is still read from the compilation rather than assumed to be
    FloorPlan. It is FloorPlan today and Eyal expects it to stay that way, so
    this is not insurance against a likely event - it just costs nothing, and
    ViewPlan.Create is happy with ceiling and structural plan types too
    (measured), so the day it is not a floor plan this needs no attention.
    """
    family = _view_family(comp_view)
    if family is None:
        return None

    group = _DEFAULT_TYPE_GROUPS.get(u"{0}".format(family))
    if group is not None:
        try:
            default_id = doc.GetDefaultElementTypeId(group)
            default_type = (
                doc.GetElement(default_id)
                if default_id not in (None, ElementId.InvalidElementId)
                else None
            )
            if default_type is not None and default_type.ViewFamily == family:
                return default_id
        except Exception:
            pass

    for candidate in FilteredElementCollector(doc).OfClass(ViewFamilyType).ToElements():
        try:
            if candidate.ViewFamily == family:
                return candidate.Id
        except Exception:
            continue
    return None


def _view_family(view):
    """The ViewFamily of a view's type, or None when it cannot be read."""
    try:
        view_type = view.Document.GetElement(view.GetTypeId())
        return view_type.ViewFamily
    except Exception:
        return None


# Which "you have no type for this" sentence fits which family. Keyed by the
# enum's NAME for the same reason _DEFAULT_TYPE_GROUPS is.
_NO_TYPE_MESSAGES = {
    u"CeilingPlan": MIRROR_NO_CEILING_TYPE,
    u"StructuralPlan": MIRROR_NO_STRUCTURAL_TYPE,
}


def _no_type_message(comp_view):
    family = _view_family(comp_view)
    if family is None:
        return MIRROR_NO_PLAN_TYPE
    return _NO_TYPE_MESSAGES.get(u"{0}".format(family), MIRROR_NO_PLAN_TYPE)


def mirror_plan(doc, comp_view, transform, level):
    """Create the planner-side twin of a comp plan. Returns (view, error, note).

    `level` comes from resolve_level and is the caller's to settle, because
    settling it can mean asking the planner a question and this runs inside a
    transaction. Must run inside one opened by the caller.

    `note` is a partial success - the view was created, but something about it
    is worth saying. Today that is only the view range.
    """
    if not isinstance(comp_view, ViewPlan):
        return None, MIRROR_UNSUPPORTED_KIND, None
    if level is None:
        return None, MIRROR_NO_GEN_LEVEL, None

    type_id = plan_type_id(doc, comp_view)
    if type_id is None:
        return None, _no_type_message(comp_view), None

    view = ViewPlan.Create(doc, type_id, level.Id)
    view.Name = _free_name(doc, comp_view.Name)
    note = _apply_plan_range(doc, view, comp_view, transform, level)
    _apply_plan_crop(view, comp_view, transform)
    return view, None, note


def resync_plan(doc, view, comp_view, transform, level):
    """Put an existing mirrored plan back on the comp plan's cut and crop.

    Same (view, rebuilt, error, note) shape as mirror_plan plus the rebuild
    flag - but a plan is far easier to follow than a section. None of what
    makes a section immovable applies: a plan's position IS its level, its view
    range and its crop, and the last two are editable.

    Two things force a rebuild rather than an edit. A change of LEVEL, because
    ViewPlan.GenLevel is fixed at creation. And a change of view FAMILY, which
    is fixed at creation too: a floor plan cannot become a Reflected Ceiling
    Plan, so a view carrying the name of a FLR-BOT slot while being a floor plan
    would otherwise be synced into the wrong family forever.
    """
    if not isinstance(view, ViewPlan) or not isinstance(comp_view, ViewPlan):
        return None, False, MIRROR_UNSUPPORTED_KIND, None
    if level is None:
        return None, False, MIRROR_NO_GEN_LEVEL, None

    current = _gen_level(view)
    if current is not None and current.Id == level.Id and _same_family(view, comp_view):
        note = _apply_plan_range(doc, view, comp_view, transform, level)
        _apply_plan_crop(view, comp_view, transform)
        return view, False, None, note

    if _placed_on_sheet(doc, view):
        return view, False, RESYNC_ON_SHEET, None

    name = view.Name
    try:
        doc.Delete(view.Id)
    except Exception as ex:
        return None, False, u"לא ניתן למחוק את המבט הישן: {0}".format(ex), None

    rebuilt, error, note = mirror_plan(doc, comp_view, transform, level)
    if rebuilt is None:
        return None, False, error, None
    rebuilt.Name = _free_name(doc, name)
    return rebuilt, True, None, note


def _same_family(view, comp_view):
    """Are these two plans the same kind of plan? Floor plan against RCP is not.

    ViewPlan is the class of a floor plan, a Reflected Ceiling Plan and a
    structural plan alike, so the class says nothing - ViewType is what
    separates them.
    """
    try:
        return view.ViewType == comp_view.ViewType
    except Exception:
        return True


def _apply_plan_range(doc, view, comp_view, transform, level):
    """Carry the comp plan's cut depth across, via ABSOLUTE elevations.

    Returns a note when the range did not make it across, None when it did.

    A view range is stored as offsets from levels, and the comp's levels are
    not this model's - so each plane is turned into an absolute elevation in
    the compilation, moved through the link, and written back as an offset from
    the one level that was matched. Nothing else has to be matched, which is
    the point: four planes could name four different levels. Resolving each
    plane against ITS OWN level is not a nicety: a new Reflected Ceiling Plan
    anchors Top and View Depth to the level ABOVE while Cut and Bottom sit on
    its own, and reading all four against one level shows an inverted range
    that does not exist.

    Only ViewDepthPlane changes meaning between a floor plan and an RCP - it is
    measured away from the viewer, so in an RCP it sits above Top rather than
    below Bottom. Top, Cut and Bottom keep their ordinary sense in both
    (measured live). Nothing here has to know that: copying plane to plane
    preserves whatever the compilation meant, and the absolute geometry with it.

    A plane set to Unlimited or to Level Above/Below carries a sentinel id
    rather than a real level; those are document-independent constants and are
    copied straight across.
    """
    comp_doc = comp_view.Document
    name = _name_of(view)
    try:
        comp_range = comp_view.GetViewRange()
        new_range = view.GetViewRange()
    except Exception as ex:
        return RANGE_NOT_APPLIED.format(name, ex)

    planned = []
    for plane in PLAN_PLANES:
        try:
            comp_level_id = comp_range.GetLevelId(plane)
            comp_level = comp_doc.GetElement(comp_level_id)
        except Exception:
            continue
        if not isinstance(comp_level, Level):
            try:
                new_range.SetLevelId(plane, comp_level_id)
            except Exception:
                pass
            continue
        try:
            absolute = transform.OfPoint(
                XYZ(0, 0, comp_level.ProjectElevation + comp_range.GetOffset(plane))
            ).Z
        except Exception:
            continue
        # Revit accepts this on all four planes, CutPlane included, even though
        # the cut plane has no level of its own in the UI (measured live). It is
        # wrapped anyway, and the whole range is abandoned if it ever refuses:
        # unwrapped, a refusal would climb out through execute_pending and roll
        # back the planner's entire batch over one view.
        try:
            new_range.SetLevelId(plane, level.Id)
        except Exception as ex:
            return RANGE_NOT_APPLIED.format(name, ex)
        planned.append((plane, absolute - level.ProjectElevation))

    # SetOffset validates nothing - not the ordering, not against the planes
    # already written (measured live, on a floor plan and on an RCP). The whole
    # range is checked once, in SetViewRange, so the offsets go in as they are
    # and there is nothing to write around.
    for plane, offset in planned:
        try:
            new_range.SetOffset(plane, offset)
        except Exception as ex:
            return RANGE_NOT_APPLIED.format(name, ex)
    try:
        view.SetViewRange(new_range)
    except Exception as ex:
        return RANGE_NOT_APPLIED.format(name, ex)
    return None


class OffAxisWarningSwallower(IFailuresPreprocessor):
    """Silences the "slightly off axis" warning that mirroring a crop raises.

    The compilation's crop is a rectangle in ITS coordinates. Moving it through
    the link transform, which is a rotation, gives a rectangle whose edges no
    longer sit on this model's axes - so Revit posts one warning per crop, and
    a planner mirroring a row's worth of views has to dismiss a stack of dialogs
    about a fact they can do nothing about and that is not a defect: the view is
    framed exactly as the coordinator framed it, which is the whole point.

    Deliberately narrow. Only the two off-axis line warnings are swallowed, by
    definition id; everything else in the transaction still reaches the planner.
    """

    def PreprocessFailures(self, failures_accessor):
        for failure in failures_accessor.GetFailureMessages():
            definition = failure.GetFailureDefinitionId()
            for swallowed in _OFF_AXIS_FAILURES:
                if swallowed == definition:
                    failures_accessor.DeleteWarning(failure)
                    break
        return FailureProcessingResult.Continue


_OFF_AXIS_FAILURES = (
    # "Line in Sketch is slightly off axis and may cause inaccuracies."
    BuiltInFailures.InaccurateFailures.InaccurateSketchLine,
    # "Line is slightly off axis and may cause inaccuracies." Same geometry,
    # reported under the plain-line definition in some contexts.
    BuiltInFailures.InaccurateFailures.InaccurateLine,
)


def suppress_off_axis_warnings(transaction):
    """Attach the swallower to a STARTED transaction. Returns it - keep it.

    Call after Start(), which is how the rest of the extension does it.
    IronPython would be free to collect the preprocessor once this returns, and
    Revit calls it long after; the caller holding it is what keeps it alive.
    """
    swallower = OffAxisWarningSwallower()
    options = transaction.GetFailureHandlingOptions()
    options.SetFailuresPreprocessor(swallower)
    transaction.SetFailureHandlingOptions(options)
    return swallower


def _apply_plan_crop(view, comp_view, transform):
    """Frame the plan exactly as the compilation framed it.

    The compilation bounds its plans with a SCOPE BOX, which the planner's
    model has no reason to contain. Rather than copy the scope box in - an
    element of the coordinator's making, in someone else's model - the shape it
    produces is copied: the crop loop, moved through the link. Same rectangle
    on screen, nothing added to the model, and a rotated scope box comes across
    as correctly as a square one because a loop carries its own orientation.
    """
    try:
        loops = comp_view.GetCropRegionShapeManager().GetCropShape()
    except Exception:
        return
    if not loops:
        return

    moved = CurveLoop()
    try:
        for curve in loops[0]:
            moved.Append(curve.CreateTransformed(transform))
    except Exception:
        return

    try:
        view.CropBoxActive = True
        view.CropBoxVisible = bool(comp_view.CropBoxVisible)
        view.GetCropRegionShapeManager().SetCropShape(moved)
    except Exception:
        pass


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
