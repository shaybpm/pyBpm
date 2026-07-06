# -*- coding: utf-8 -*-
""" Section creation for Get Bpm Sections.

Moved verbatim (adapted to take `doc` explicitly) from the original
GetBpmSections pushbutton so it can be reused by the modeless results UI: the
grid uses find_existing_section / get_host_view_names for the "exists" column
(read only), and the Create action (Phase 4, via External Event) calls
create_section. create_section does NOT open a transaction - the caller wraps
it (as the original run() did). IronPython 2.7. """

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    ViewFamilyType,
    View,
    ViewSection,
    BoundingBoxXYZ,
    Transform,
    XYZ,
    ElementTypeGroup,
    BuiltInParameter,
)
from pyrevit import forms
from pyrevit.forms import alert

import RevitUtils, pyUtils

TARGET_PREFIX = "BPM_Section_"


def target_section_name(su_name):
    return TARGET_PREFIX + su_name


def get_all_views(doc):
    return FilteredElementCollector(doc).OfClass(View).ToElements()


def get_host_view_names(doc):
    """Set of all view names in the host doc (used for a fast exists check)."""
    return set(view.Name for view in get_all_views(doc))


def find_existing_section(doc, su_name):
    """Return the host-model view named exactly BPM_Section_<su_name>, or None."""
    target = target_section_name(su_name)
    for view in get_all_views(doc):
        if view.Name == target:
            return view
    return None


def is_viewName_already_exists(all_views, viewName):
    for view in all_views:
        if view.Name == viewName:
            return True
    return False


def get_all_section_viewFamilyTypes(doc):
    all_viewFamilyTypes = (
        FilteredElementCollector(doc).OfClass(ViewFamilyType).ToElements()
    )
    section_viewFamilyTypes = []
    for viewFamilyType in all_viewFamilyTypes:
        if viewFamilyType.FamilyName == "Section":
            section_viewFamilyTypes.append(viewFamilyType)
    return section_viewFamilyTypes


def get_type_id(doc):
    default_viewFamilyType_id = doc.GetDefaultElementTypeId(
        ElementTypeGroup.ViewTypeSection
    )
    if default_viewFamilyType_id:
        return default_viewFamilyType_id

    section_viewFamilyTypes = get_all_section_viewFamilyTypes(doc)
    section_viewFamilyTypes_names = [
        RevitUtils.getElementName(viewFamilyType)
        for viewFamilyType in section_viewFamilyTypes
    ]
    selected_viewFamilyType_str = forms.SelectFromList.show(
        section_viewFamilyTypes_names,
        title="Select Section Type",
        button_name="Select",
        multiselect=False,
    )
    if not selected_viewFamilyType_str:
        return None
    selected_viewFamilyType = pyUtils.findInList(
        section_viewFamilyTypes,
        lambda viewFamilyType: RevitUtils.getElementName(viewFamilyType)
        == selected_viewFamilyType_str,
    )
    return selected_viewFamilyType.Id


def create_section(doc, section, viewFamilyTypeId, transform):
    view_direction = -1 * transform.OfVector(section.ViewDirection)
    up_direction = transform.OfVector(section.UpDirection)
    right_direction = -1 * transform.OfVector(section.RightDirection)

    view_crop_region_CurveLoopIterator = (
        section.GetCropRegionShapeManager().GetCropShape()[0].GetCurveLoopIterator()
    )
    view_crop_region_CurveLoopIterator.MoveNext()
    point1 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)
    view_crop_region_CurveLoopIterator.MoveNext()
    point2 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)
    view_crop_region_CurveLoopIterator.MoveNext()
    point3 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)
    view_crop_region_CurveLoopIterator.MoveNext()
    point4 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)

    point1 = transform.OfPoint(point1)
    point2 = transform.OfPoint(point2)
    point3 = transform.OfPoint(point3)
    point4 = transform.OfPoint(point4)

    points = [point1, point2, point3, point4]

    section_height = None
    section_length = None
    for i in range(len(points)):
        next = i + 1 if i < len(points) - 1 else 0
        v = points[next] - points[i]
        if not section_height and v.DotProduct(right_direction) == 0:
            section_height = v.GetLength()
        if not section_length and v.DotProduct(up_direction) == 0:
            section_length = v.GetLength()

    if not section_height or not section_length:
        alert("Couldn't calculate section height and length.")
        return

    section_far_clip = section.get_Parameter(
        BuiltInParameter.VIEWER_BOUND_OFFSET_FAR
    ).AsDouble()

    xyz_min = XYZ(-0.5 * section_length, -0.5 * section_height, -0.5 * section_far_clip)
    xyz_max = XYZ(0.5 * section_length, 0.5 * section_height, 0.5 * section_far_clip)

    mid_point = (point1 + point2 + point3 + point4) / 4
    mid_point = mid_point + 0.5 * section_far_clip * view_direction

    section_box = BoundingBoxXYZ()
    section_box.Enabled = True

    t = Transform.Identity
    t.Origin = mid_point
    t.BasisZ = view_direction
    t.BasisY = up_direction
    t.BasisX = right_direction

    section_box.Transform = t
    section_box.Min = xyz_min
    section_box.Max = xyz_max

    new_section = ViewSection.CreateSection(doc, viewFamilyTypeId, section_box)
    new_section_name = target_section_name(section.Name)
    num = 0
    all_views = get_all_views(doc)
    loop_count = 0
    max_loop_count = 1000
    while is_viewName_already_exists(all_views, new_section_name):
        if loop_count > max_loop_count:
            raise Exception("Couldn't create new section with name: " + new_section_name)
        loop_count += 1
        num += 1
        new_section_name = target_section_name(section.Name) + "_" + str(num)
    new_section.Name = new_section_name
    return new_section
