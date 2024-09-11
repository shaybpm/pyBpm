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
    ElementId,
    BuiltInParameter,
)

from pyrevit import script, forms

from RevitUtils import (
    getOutlineByBoundingBox,
    get_all_link_instances,
    is_wall_concrete,
    get_levels_sorted,
    get_solid_from_element,
    get_level_bounding_boxes,
)
from RevitUtilsOpenings import get_opening_element_filter
from ServerUtils import ProjectStructuralModels

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

project_structural_models = ProjectStructuralModels(doc)

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


class IntersectWithConcreteResult:
    def __init__(self, intersect_element, intersect_bounding_box, transform=None):
        self.intersect_element = intersect_element
        self.intersect_bounding_box = intersect_bounding_box
        self.transform = transform


class ElementResult:
    def __init__(self, mep_element, found_in_level_id):
        self.mep_element = mep_element
        self.intersect_with_concrete_result = []
        self.found_in_level_id = found_in_level_id

    def is_intersect_with_concrete(self):
        return len(self.intersect_with_concrete_result) > 0


def get_all_MEP_elements(bbox_to_filter=None):
    for b_i_category in [
        BuiltInCategory.OST_DuctCurves,
        BuiltInCategory.OST_PipeCurves,
        BuiltInCategory.OST_CableTray,
        # fittings:
        BuiltInCategory.OST_DuctFitting,
        BuiltInCategory.OST_PipeFitting,
        BuiltInCategory.OST_CableTrayFitting,
    ]:
        element_collector = (
            FilteredElementCollector(doc)
            .OfCategory(b_i_category)
            .WhereElementIsNotElementType()
        )
        if bbox_to_filter:
            outline = getOutlineByBoundingBox(bbox_to_filter)
            bbox_intersect_filter = BoundingBoxIntersectsFilter(outline)
            bbox_inside_filter = BoundingBoxIsInsideFilter(outline)
            bbox_filter = LogicalOrFilter(bbox_intersect_filter, bbox_inside_filter)
            element_collector.WherePasses(bbox_filter)
        elements = element_collector.ToElements()
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


def get_thickness_of_vertical_element(element):
    """
    Works for walls, columns and beams.
    For columns, returns the minimum.
    """
    if element.Category.Id == ElementId(BuiltInCategory.OST_Walls):
        return element.Width if hasattr(element, "Width") else 0
    if element.Category.Id == ElementId(BuiltInCategory.OST_StructuralColumns):
        bbox = element.get_BoundingBox(None)
        if not bbox:
            return 0
        delta_x = bbox.Max.X - bbox.Min.X
        delta_y = bbox.Max.Y - bbox.Min.Y
        return min(delta_x, delta_y)
    if element.Category.Id == ElementId(BuiltInCategory.OST_StructuralFraming):
        bbox = element.get_BoundingBox(None)
        if not bbox:
            return 0
        # TODO: Find better way to get the thickness of the beam
        delta_x = bbox.Max.X - bbox.Min.X
        delta_y = bbox.Max.Y - bbox.Min.Y
        return min(delta_x, delta_y)


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
        BuiltInCategory.OST_StructuralColumns,
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

            # check if the intersect is inside the element
            # - if its a floor, the delta z of the bbox need to be at last as the height of the floor
            # - if its a wall or a beam, the delta x or delta y of the bbox need to be at last as the thickness of the wall

            intersect_bounding_box = solid_intersect.GetBoundingBox()
            if category == BuiltInCategory.OST_Floors:
                floor_thickness_param = element.get_Parameter(
                    BuiltInParameter.FLOOR_ATTR_THICKNESS_PARAM
                )
                if floor_thickness_param:
                    floor_thickness = floor_thickness_param.AsDouble()
                    if floor_thickness:
                        intersect_delta_z = (
                            intersect_bounding_box.Max.Z - intersect_bounding_box.Min.Z
                        )
                        if intersect_delta_z < floor_thickness:
                            continue
            else:
                pass
                # thickness = get_thickness_of_vertical_element(element)
                # if thickness:
                #     intersect_delta_x = (
                #         intersect_bounding_box.Max.X - intersect_bounding_box.Min.X
                #     )
                #     intersect_delta_y = (
                #         intersect_bounding_box.Max.Y - intersect_bounding_box.Min.Y
                #     )
                #     if intersect_delta_x < thickness and intersect_delta_y < thickness:
                #         continue

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


def get_is_mep_without_opening_intersect_with_concrete(mep_element, found_in_level_id):
    result = ElementResult(mep_element, found_in_level_id)

    doc_guid = doc.GetCloudModelPath().GetModelGUID().ToString()
    if doc_guid in project_structural_models.structural_models:
        find_concrete_intersect(doc, result)

    all_links = get_all_link_instances(doc)
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue
        link_doc_guid = link_doc.GetCloudModelPath().GetModelGUID().ToString()
        if link_doc_guid not in project_structural_models.structural_models:
            continue

        find_concrete_intersect(link_doc, result, link.GetTotalTransform())

    return result


def is_structural_model_exists():
    all_links = get_all_link_instances(doc)
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue
        link_doc_guid = link_doc.GetCloudModelPath().GetModelGUID().ToString()
        if link_doc_guid in project_structural_models.structural_models:
            return True
    return False


def run():
    if not doc.IsModelInCloud:
        forms.alert("This model is not in the cloud.")
        return

    if not is_structural_model_exists():
        forms.alert(
            "No structural model was found in model.\nPlease make sure that the structural model is loaded, open the settings dialog and add a structural model."
        )
        return

    level_bounding_boxes = get_level_bounding_boxes(doc)

    relevant_results = []

    levels = get_levels_sorted(doc)
    levels_id_name_dict = {l.Id: l.Name for l in levels}
    selected_levels = forms.SelectFromList.show(
        levels_id_name_dict.values(), title="Select Levels", multiselect=True
    )
    if not selected_levels:
        return

    for level_bbox in level_bounding_boxes:
        level_id = level_bbox["level_id"]
        if level_id not in levels_id_name_dict:
            continue
        if levels_id_name_dict[level_id] not in selected_levels:
            continue

        mep_elements = get_all_MEP_elements(level_bbox["bbox"])
        for mep_element in mep_elements:
            if mep_element.Id in [r.mep_element.Id for r in relevant_results]:
                continue

            result = get_is_mep_without_opening_intersect_with_concrete(
                mep_element, level_id
            )
            if result.is_intersect_with_concrete():
                relevant_results.append(result)

    if len(relevant_results) == 0:
        forms.alert("No missing openings were found.")
        return

    dialog = MepOpeningMonitorDialog(uidoc, relevant_results)
    dialog.Show()


run()
