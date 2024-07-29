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

from RevitUtils import getOutlineByBoundingBox, get_all_link_instances

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

# debug_ids = [1616301]


# def to_print_debug_info(element):
#     return element.Id.IntegerValue in debug_ids


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


def is_concrete_there(document, bbox_intersects_filter):
    walls_count = (
        FilteredElementCollector(document)
        .OfCategory(BuiltInCategory.OST_Walls)
        .WherePasses(bbox_intersects_filter)
        .GetElementCount()
    )
    if walls_count > 0:
        return True

    floors_count = (
        FilteredElementCollector(document)
        .OfCategory(BuiltInCategory.OST_Floors)
        .WherePasses(bbox_intersects_filter)
        .GetElementCount()
    )
    if floors_count > 0:
        return True


def is_mep_without_opening_intersect_with_concrete(mep_element):
    bounding_box = mep_element.get_BoundingBox(None)
    if not bounding_box:
        return False

    outline = getOutlineByBoundingBox(bounding_box)
    bbox_intersects_filter = BoundingBoxIntersectsFilter(outline)

    if is_opening_there(doc, bbox_intersects_filter):
        return False

    if is_concrete_there(doc, bbox_intersects_filter):
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

        if is_concrete_there(link_doc, bbox_intersects_filter):
            return True

    return False


def run():
    output_elements = []

    for mep_element in get_all_MEP_elements():
        if not is_mep_without_opening_intersect_with_concrete(mep_element):
            output_elements.append(mep_element)

    likifies = [output.linkify(element.Id) for element in output_elements]
    output.print_html(
        "<h1>MEP elements without openings intersecting with concrete:</h1>"
    )
    output.print_html("<br>".join(likifies))


run()
