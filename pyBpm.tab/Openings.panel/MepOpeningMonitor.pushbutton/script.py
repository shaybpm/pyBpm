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
    BoundingBoxIsInsideFilter,
    BoundingBoxIntersectsFilter,
    LogicalOrFilter,
    BooleanOperationsUtils,
    BooleanOperationsType,
)

from pyrevit import script, forms

from RevitUtils import (
    getOutlineByBoundingBox,
    get_all_link_instances,
    is_wall_concrete,
    get_levels_sorted,
    get_solid_from_element,
)
from RevitUtilsOpenings import get_opening_element_filter

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))
from MepOpeningMonitorDialog import MepOpeningMonitorDialog  # type: ignore

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


class IntersectWithConcreteResult:
    def __init__(self, intersect_element, intersect_bounding_box, transform=None):
        self.intersect_element = intersect_element
        self.intersect_bounding_box = intersect_bounding_box
        self.transform = transform


class ElementResult:
    def __init__(self, mep_element):
        self.mep_element = mep_element
        self.intersect_with_concrete_result = []

    @property
    def is_intersect_with_concrete(self):
        return len(self.intersect_with_concrete_result) > 0


def get_all_MEP_elements():
    for b_i_category in [
        BuiltInCategory.OST_DuctCurves,
        BuiltInCategory.OST_PipeCurves,
        BuiltInCategory.OST_CableTray,
        # fittings:
        BuiltInCategory.OST_DuctFitting,
        BuiltInCategory.OST_PipeFitting,
        BuiltInCategory.OST_CableTrayFitting,
    ]:
        elements = (
            FilteredElementCollector(doc)
            .OfCategory(b_i_category)
            .WhereElementIsNotElementType()
            .ToElements()
        )
        for element in elements:
            yield element


def is_opening_there(element_filter):
    opening_element_filter = get_opening_element_filter(doc)
    openings_count = (
        FilteredElementCollector(doc)
        .WherePasses(opening_element_filter)
        .WherePasses(element_filter)
        .GetElementCount()
    )
    return openings_count > 0


def find_concrete_intersect(document_to_search, result, transform=None):
    bbox = result.mep_element.get_BoundingBox(None)
    if not bbox:
        return

    solid = (
        get_solid_from_element(result.mep_element, transform.Inverse)
        if transform
        else get_solid_from_element(result.mep_element)
    )
    if not solid:
        return

    outline = (
        getOutlineByBoundingBox(bbox, transform.Inverse)
        if transform
        else getOutlineByBoundingBox(bbox)
    )
    bbox_intersects_filter = BoundingBoxIntersectsFilter(outline)

    categories = [
        BuiltInCategory.OST_Walls,
        BuiltInCategory.OST_Floors,
        BuiltInCategory.OST_StructuralFraming,
    ]

    error_message_printed = False

    for category in categories:
        elements = (
            FilteredElementCollector(document_to_search)
            .OfCategory(category)
            .WherePasses(bbox_intersects_filter)
            .ToElements()
        )
        for element in elements:
            if category == BuiltInCategory.OST_Walls and not is_wall_concrete(element):
                continue

            if hasattr(result.mep_element.Location, "Curve"):
                z_direction = result.mep_element.Location.Curve.Direction.Z
                if category == BuiltInCategory.OST_Floors:
                    if -0.5 <= z_direction <= 0.5:
                        continue
                else:
                    if not (-0.5 <= z_direction <= 0.5):
                        continue

            bbox_element = element.get_BoundingBox(None)
            if not bbox_element:
                continue

            solid_element = get_solid_from_element(element)
            if not solid_element:
                continue

            try:
                solid_intersect = BooleanOperationsUtils.ExecuteBooleanOperation(
                    solid,
                    solid_element,
                    BooleanOperationsType.Intersect,
                )
            except:
                if not error_message_printed:
                    output.print_html(
                        "<h3>Error in element: {}</h3>".format(
                            output.linkify(result.mep_element.Id)
                        )
                    )
                    error_message_printed = True
                continue

            if solid_intersect.Volume == 0:
                continue

            # TODO: separate the solid and do the following code for each solid.

            intersect_bounding_box = solid_intersect.GetBoundingBox()
            intersect_outline = getOutlineByBoundingBox(
                intersect_bounding_box, transform
            )
            intersect_bbox_intersects_filter = BoundingBoxIntersectsFilter(
                intersect_outline
            )
            intersect_bbox_is_inside_filter = BoundingBoxIsInsideFilter(
                intersect_outline
            )
            intersect_bbox_filter = LogicalOrFilter(
                intersect_bbox_intersects_filter, intersect_bbox_is_inside_filter
            )
            if is_opening_there(intersect_bbox_filter):
                continue

            result.intersect_with_concrete_result.append(
                IntersectWithConcreteResult(element, intersect_bounding_box, transform)
            )


def get_is_mep_without_opening_intersect_with_concrete(mep_element):
    result = ElementResult(mep_element)

    find_concrete_intersect(doc, result)

    all_links = get_all_link_instances(doc)
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue

        find_concrete_intersect(link_doc, result, link.GetTotalTransform())

    return result


def run():
    relevant_results = []

    levels = get_levels_sorted(doc)
    levels_id_name_dict = {l.Id: l.Name for l in levels}
    selected_levels = forms.SelectFromList.show(
        levels_id_name_dict.values(), title="Select Levels", multiselect=True
    )
    if not selected_levels:
        return

    for mep_element in get_all_MEP_elements():
        if levels_id_name_dict[mep_element.LevelId] not in selected_levels:
            continue

        result = get_is_mep_without_opening_intersect_with_concrete(mep_element)
        if result.is_intersect_with_concrete:
            relevant_results.append(result)

    if len(relevant_results) == 0:
        forms.alert("No missing openings were found.")
        return

    dialog = MepOpeningMonitorDialog(uidoc, relevant_results)
    dialog.Show()


run()
