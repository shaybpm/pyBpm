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

from RevitUtils import (
    getOutlineByBoundingBox,
    get_all_link_instances,
    is_wall_concrete,
    get_levels_sorted,
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


class ElementResult:
    def __init__(self, mep_element):
        self.mep_element = mep_element
        self.is_bounding_box_found = None
        self.is_opening_there = None
        self.is_intersect_with_concrete = None
        self.concrete_category_name = None

    @property
    def finely_result(self):
        return not self.is_opening_there and self.is_intersect_with_concrete


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


def get_is_concrete_there(document, bbox_intersects_filter, result):
    walls_elements = (
        FilteredElementCollector(document)
        .OfCategory(BuiltInCategory.OST_Walls)
        .WherePasses(bbox_intersects_filter)
        .ToElements()
    )
    for wall in walls_elements:
        if is_wall_concrete(wall):
            result.is_intersect_with_concrete = True
            result.concrete_category_name = "Wall"
            return True

    floors_count = (
        FilteredElementCollector(document)
        .OfCategory(BuiltInCategory.OST_Floors)
        .WherePasses(bbox_intersects_filter)
        .GetElementCount()
    )
    if floors_count > 0:
        result.is_intersect_with_concrete = True
        result.concrete_category_name = "Floor"
        return True

    beams_count = (
        FilteredElementCollector(document)
        .OfCategory(BuiltInCategory.OST_StructuralFraming)
        .WherePasses(bbox_intersects_filter)
        .GetElementCount()
    )
    if beams_count > 0:
        result.is_intersect_with_concrete = True
        result.concrete_category_name = "Structural Framing"
        return True

    return False


def get_is_mep_without_opening_intersect_with_concrete(mep_element):
    result = ElementResult(mep_element)

    bounding_box = mep_element.get_BoundingBox(None)
    if not bounding_box:
        result.is_bounding_box_found = False
        return result
    result.is_bounding_box_found = True

    outline = getOutlineByBoundingBox(bounding_box)
    bbox_intersects_filter = BoundingBoxIntersectsFilter(outline)

    if is_opening_there(bbox_intersects_filter):
        result.is_opening_there = True
        return result
    result.is_opening_there = False

    if get_is_concrete_there(doc, bbox_intersects_filter, result):
        return result

    all_links = get_all_link_instances(doc)
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue

        outline = getOutlineByBoundingBox(
            bounding_box, link.GetTotalTransform().Inverse
        )
        bbox_intersects_filter = BoundingBoxIntersectsFilter(outline)

        if get_is_concrete_there(link_doc, bbox_intersects_filter, result):
            return result

    result.is_intersect_with_concrete = False
    return result


def run():
    relevant_results = []

    for mep_element in get_all_MEP_elements():
        result = get_is_mep_without_opening_intersect_with_concrete(mep_element)
        if result.finely_result:
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
                if res.concrete_category_name == "Floor":
                    row[1].append(
                        output.linkify(res.mep_element.Id, res.mep_element.Name)
                    )
                elif res.concrete_category_name == "Wall":
                    row[2].append(
                        output.linkify(res.mep_element.Id, res.mep_element.Name)
                    )
                elif res.concrete_category_name == "Structural Framing":
                    row[3].append(
                        output.linkify(res.mep_element.Id, res.mep_element.Name)
                    )
        row[1] = "<br>".join(row[1]) if row[1] else "✅"
        row[2] = "<br>".join(row[2]) if row[2] else "✅"
        row[3] = "<br>".join(row[3]) if row[3] else "✅"
        table_data.append(row)

    print_table(output, columns, table_data)


run()
