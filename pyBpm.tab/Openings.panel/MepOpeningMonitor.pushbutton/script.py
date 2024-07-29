# -*- coding: utf-8 -*-
""" Monitor MEP penetrating concrete without openings modeling """
__title__ = "MEP Opening\nMonitor"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    BuiltInCategory,
    BoundingBoxIntersectsFilter,
)

from pyrevit import script

from RevitUtils import getOutlineByBoundingBox, get_all_link_instances, is_wall_concrete

from RevitUtilsOpenings import get_opening_element_filter

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document
output = script.get_output()
output.close_others()

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------
# TODO: In the output, divide to levels and walls+beams or floors.
# EXTREME TODO: marge elements that are connect to each other to one linkify.


def get_all_MEP_elements():
    for b_i_category in [
        BuiltInCategory.OST_DuctCurves,
        BuiltInCategory.OST_PipeCurves,
        BuiltInCategory.OST_CableTray,
    ]:
        elements = (
            FilteredElementCollector(doc)
            .OfCategory(b_i_category)
            .WhereElementIsNotElementType()
            .ToElements()
        )
        for element in elements:
            yield element


def is_opening_there(document, bbox_intersects_filter):
    opening_element_filter = get_opening_element_filter(doc)
    openings_count = (
        FilteredElementCollector(document)
        .WherePasses(opening_element_filter)
        .WherePasses(bbox_intersects_filter)
        .GetElementCount()
    )
    return openings_count > 0


def is_concrete_there(document, bbox_intersects_filter, print_debug=False):
    walls_elements = (
        FilteredElementCollector(document)
        .OfCategory(BuiltInCategory.OST_Walls)
        .WherePasses(bbox_intersects_filter)
        .ToElements()
    )
    for wall in walls_elements:
        if is_wall_concrete(wall):
            return True

    floors_count = (
        FilteredElementCollector(document)
        .OfCategory(BuiltInCategory.OST_Floors)
        .WherePasses(bbox_intersects_filter)
        .GetElementCount()
    )
    if floors_count > 0:
        if print_debug:
            print("Floor is there")
        return True

    beams_count = (
        FilteredElementCollector(document)
        .OfCategory(BuiltInCategory.OST_StructuralFraming)
        .WherePasses(bbox_intersects_filter)
        .GetElementCount()
    )
    if beams_count > 0:
        if print_debug:
            print("Beam is there")
        return True

    if print_debug:
        print("No concrete is there")
    return False


def is_mep_without_opening_intersect_with_concrete(mep_element):
    print_debug = mep_element.Id.IntegerValue in []

    bounding_box = mep_element.get_BoundingBox(None)
    if not bounding_box:
        return False

    outline = getOutlineByBoundingBox(bounding_box)
    bbox_intersects_filter = BoundingBoxIntersectsFilter(outline)

    if is_opening_there(doc, bbox_intersects_filter):
        return False

    if is_concrete_there(doc, bbox_intersects_filter, print_debug=print_debug):
        return True

    all_links = get_all_link_instances(doc)
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue

        outline = getOutlineByBoundingBox(
            bounding_box, link.GetTotalTransform().Inverse
        )
        bbox_intersects_filter = BoundingBoxIntersectsFilter(outline)

        if is_concrete_there(link_doc, bbox_intersects_filter, print_debug=print_debug):
            return True

    return False


def run():
    output_elements = []

    for mep_element in get_all_MEP_elements():
        if is_mep_without_opening_intersect_with_concrete(mep_element):
            output_elements.append(mep_element)

    likifies = [output.linkify(element.Id) for element in output_elements]
    output.print_html(
        "<h1>MEP elements without openings intersecting with concrete:</h1>"
    )
    output.print_html("<br>".join(likifies))


run()
