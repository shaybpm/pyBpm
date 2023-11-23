# -*- coding: utf-8 -*-
""" Create selected section from the Bpm suggested sections.

To run this script on multiple sections, hold Shift while selecting the sections. """
__title__ = "Get Bpm\nSections"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import (
    Transaction,
    FilteredElementCollector,
    RevitLinkInstance,
    ViewType,
    BuiltInParameter,
    View,
    ViewSection,
    ViewFamilyType,
    BoundingBoxXYZ,
    Transform,
    XYZ,
    ElementTypeGroup,
)

from Autodesk.Revit.UI import TaskDialog

from pyrevit import forms

import sys, os

root_path = __file__[: __file__.rindex(".extension") + len(".extension")]
sys.path.append(os.path.join(root_path, "lib"))
import RevitUtils, pyUtils  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

transaction_name = "BPM | Get Bpm Section"


def alert(msg):
    TaskDialog.Show(transaction_name, msg)


multiple_sections = __shiftclick__  # type: ignore

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def is_su_sec(view):
    if not view.ViewType:
        return False

    if not view.ViewType == ViewType.Section:
        return False

    if not "SU" in view.Name:
        return False

    viewport_sheet_number = view.get_Parameter(BuiltInParameter.VIEWPORT_SHEET_NUMBER)
    if not viewport_sheet_number.AsString():
        return False

    return True


def get_all_section_viewFamilyTypes():
    all_viewFamilyTypes = (
        FilteredElementCollector(doc).OfClass(ViewFamilyType).ToElements()
    )
    section_viewFamilyTypes = []
    for viewFamilyType in all_viewFamilyTypes:
        if viewFamilyType.FamilyName == "Section":
            section_viewFamilyTypes.append(viewFamilyType)
    return section_viewFamilyTypes


def get_all_views():
    return FilteredElementCollector(doc).OfClass(View).ToElements()


def is_viewName_already_exists(all_views, viewName):
    for view in all_views:
        if view.Name == viewName:
            return True
    return False


def create_section(section, viewFamilyTypeId, transform):
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
    new_section_name = "BPM_Section_" + section.Name
    num = 0
    all_views = get_all_views()
    loop_count = 0
    max_loop_count = 1000
    while is_viewName_already_exists(all_views, new_section_name):
        if loop_count > max_loop_count:
            raise Exception(
                "Couldn't create new section with name: " + new_section_name
            )
        loop_count += 1
        num += 1
        new_section_name = "BPM_Section_" + section.Name + "_" + str(num)
    new_section.Name = new_section_name
    return new_section


def get_type_id():
    default_viewFamilyType_id = doc.GetDefaultElementTypeId(
        ElementTypeGroup.ViewTypeSection
    )
    if default_viewFamilyType_id:
        return default_viewFamilyType_id

    section_viewFamilyTypes = get_all_section_viewFamilyTypes()
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


def run():
    comp_link = RevitUtils.get_comp_link(doc)
    if not comp_link:
        alert("The Compilation model link is not loaded.")
        return
    comp_doc = comp_link.GetLinkDocument()
    if not comp_doc:
        alert("Something went wrong with the Compilation model link.")
        return
    selected_section = forms.select_views(
        title="Select Plans",
        button_name="Copy",
        width=500,
        multiple=multiple_sections,
        filterfunc=is_su_sec,
        doc=comp_doc,
    )

    if not selected_section:
        return

    if not multiple_sections:
        selected_section = [selected_section]

    viewFamily_type_id = get_type_id()
    if not viewFamily_type_id:
        return

    new_views = []
    transaction_name_info = (
        selected_section[0].Name if len(selected_section) == 1 else "Multiple Sections"
    )
    t = Transaction(doc, transaction_name + " - " + transaction_name_info)
    t.Start()
    for section in selected_section:
        new_view = create_section(
            section, viewFamily_type_id, comp_link.GetTotalTransform()
        )
        new_views.append(new_view)
    t.Commit()

    if new_views and len(new_views) == 1:
        new_view = new_views[0]
        uidoc.ActiveView = new_view


run()
