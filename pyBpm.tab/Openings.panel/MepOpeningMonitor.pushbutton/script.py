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
    Transform,
)

from pyrevit import script

from RevitUtils import (
    getOutlineByBoundingBox,
    get_all_link_instances,
    is_wall_concrete,
    get_levels_sorted,
    get_intersect_bounding_box,
)
from PyRevitUtils import print_table
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


class IntersectWithConcreteResult:
    def __init__(self, intersect_element, intersect_bounding_box):
        self.intersect_element = intersect_element
        self.intersect_bounding_box = intersect_bounding_box


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


def is_opening_there(bbox_intersects_filter):
    opening_element_filter = get_opening_element_filter(doc)
    openings_count = (
        FilteredElementCollector(doc)
        .WherePasses(opening_element_filter)
        .WherePasses(bbox_intersects_filter)
        .GetElementCount()
    )
    return openings_count > 0


def find_concrete_intersect(document, bbox, result, transform=None):
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

    for category in categories:
        elements = (
            FilteredElementCollector(document)
            .OfCategory(category)
            .WherePasses(bbox_intersects_filter)
            .ToElements()
        )
        for element in elements:
            if category == BuiltInCategory.OST_Walls and not is_wall_concrete(element):
                continue
            bbox_element = element.get_BoundingBox(None)
            if not bbox_element:
                continue
            intersect_bounding_box = (
                get_intersect_bounding_box(bbox, bbox_element, transform)
                if transform
                else get_intersect_bounding_box(bbox, bbox_element)
            )
            intersect_outline = getOutlineByBoundingBox(bbox_element)
            element_bbox_intersects_filter = BoundingBoxIntersectsFilter(
                intersect_outline
            )
            if is_opening_there(element_bbox_intersects_filter):
                continue
            result.intersect_with_concrete_result.append(
                IntersectWithConcreteResult(element, intersect_bounding_box)
            )


def get_is_mep_without_opening_intersect_with_concrete(mep_element):
    result = ElementResult(mep_element)

    bounding_box = mep_element.get_BoundingBox(None)
    if not bounding_box:
        return result

    find_concrete_intersect(doc, bounding_box, result)

    all_links = get_all_link_instances(doc)
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue

        find_concrete_intersect(
            link_doc, bounding_box, result, link.GetTotalTransform()
        )

    return result


def run():
    relevant_results = []

    for mep_element in get_all_MEP_elements():
        result = get_is_mep_without_opening_intersect_with_concrete(mep_element)
        if result.is_intersect_with_concrete:
            relevant_results.append(result)

    columns = [
        "Level",
        "Floor",
        "Wall",
        "Structural Framing",
    ]

    levels = get_levels_sorted(doc)

    table_data = []
    for level in levels:
        row = [level.Name, [], [], []]
        for res in relevant_results:
            if res.mep_element.LevelId == level.Id:
                for intersect_res in res.intersect_with_concrete_result:
                    if intersect_res.intersect_element.Category.Name == "Walls":
                        row[2].append(
                            output.linkify(
                                res.mep_element.Id,
                                res.mep_element.Name,
                            )
                        )
                    elif intersect_res.intersect_element.Category.Name == "Floors":
                        row[1].append(
                            output.linkify(
                                res.mep_element.Id,
                                res.mep_element.Name,
                            )
                        )
                    elif (
                        intersect_res.intersect_element.Category.Name
                        == "Structural Framing"
                    ):
                        row[3].append(
                            output.linkify(
                                res.mep_element.Id,
                                res.mep_element.Name,
                            )
                        )
        row[1] = "<br>".join(row[1]) if row[1] else "✅"
        row[2] = "<br>".join(row[2]) if row[2] else "✅"
        row[3] = "<br>".join(row[3]) if row[3] else "✅"
        table_data.append(row)

    print_table(output, columns, table_data)


run()
