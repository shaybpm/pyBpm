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
    get_min_max_points_from_bbox,
)
from RevitUtilsOpenings import get_opening_element_filter
from ServerUtils import ProjectStructuralModels

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))
from MepOpeningMonitorDialog import MepOpeningMonitorDialog  # type: ignore
from PreFiltersDialog import PreFiltersDialog  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document
output = script.get_output()
output.close_others()

project_structural_models = ProjectStructuralModels(doc)
opening_element_filter = get_opening_element_filter(doc)

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


class IntersectWithConcreteResult:
    def __init__(
        self, intersect_element, intersect_bounding_box, level_id, transform=None
    ):
        self.intersect_element = intersect_element
        self.intersect_bounding_box = intersect_bounding_box
        self.transform = transform
        self.level_id = level_id


class ElementResult:
    def __init__(self, mep_element):
        self.mep_element = mep_element
        self.intersect_with_concrete_result = []

    def is_intersect_with_concrete(self):
        return len(self.intersect_with_concrete_result) > 0


def get_MEP_elements_within_bbox(bbox_to_filter=None):
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
    openings_count = (
        FilteredElementCollector(doc)
        .WherePasses(opening_element_filter)
        .WherePasses(element_filter)
        .GetElementCount()
    )
    return openings_count > 0


def find_concrete_intersect(
    document_to_search, result, level_bounding_boxes, transform=None
):
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
        BuiltInCategory.OST_Stairs,
        BuiltInCategory.OST_StairsLandings,
        BuiltInCategory.OST_Ramps,
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

            if hasattr(result.mep_element.Location, "Curve") and category in [
                BuiltInCategory.OST_Walls,
                BuiltInCategory.OST_Floors,
                BuiltInCategory.OST_StructuralFraming,
                BuiltInCategory.OST_StructuralColumns,
                BuiltInCategory.OST_StairsLandings,
            ]:
                z_direction = result.mep_element.Location.Curve.Direction.Z
                term = -0.5 <= z_direction <= 0.5
                if (
                    category == BuiltInCategory.OST_Floors
                    or category == BuiltInCategory.OST_StairsLandings
                ):
                    if term:
                        continue
                else:
                    if not term:
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

            intersect_bounding_box = solid_intersect.GetBoundingBox()

            level_id = None
            intersect_min, intersect_max = get_min_max_points_from_bbox(
                intersect_bounding_box, transform.Inverse
            )
            intersect_center_point = (intersect_min + intersect_max) / 2
            for level_bbox in level_bounding_boxes:
                level_outline = getOutlineByBoundingBox(level_bbox["bbox"])
                if level_outline.Contains(intersect_center_point, 0.1):
                    level_id = level_bbox["level_id"]
                    break
            if not level_id:
                continue

            # check if the intersect is inside the element
            # - if its a floor, the delta z of the bbox need to be at last as the height of the floor
            # - if its a wall or a beam, the delta x or delta y of the bbox need to be at last as the thickness of the wall

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
                # TODO: Avoid elements that are parallel to the MEP element
                pass

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
                IntersectWithConcreteResult(
                    element, intersect_bounding_box, level_id, transform
                )
            )


def get_is_mep_without_opening_intersect_with_concrete(
    mep_element, level_bounding_boxes
):
    result = ElementResult(mep_element)

    doc_guid = doc.GetCloudModelPath().GetModelGUID().ToString()
    if doc_guid in project_structural_models.structural_models:
        find_concrete_intersect(doc, result, level_bounding_boxes)

    all_links = get_all_link_instances(doc)
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue
        link_doc_guid = link_doc.GetCloudModelPath().GetModelGUID().ToString()
        if link_doc_guid not in project_structural_models.structural_models:
            continue

        find_concrete_intersect(
            link_doc, result, level_bounding_boxes, link.GetTotalTransform()
        )

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

    if not opening_element_filter:
        forms.alert(
            "No opening families were found in the model.\nPlease make sure that the model contains the BPM openings families."
        )

    relevant_results = []

    pre_filters_res = PreFiltersDialog(doc).show_dialog()
    if not pre_filters_res:
        return
    selected_level_ids = pre_filters_res["levels"]
    if not selected_level_ids:
        return

    level_bounding_boxes = get_level_bounding_boxes(doc)
    level_bounding_boxes_filtered = []
    for level_bbox in level_bounding_boxes:
        level_id = level_bbox["level_id"]
        if level_id not in selected_level_ids:
            continue
        level_bounding_boxes_filtered.append(level_bbox)

    for level_bbox in level_bounding_boxes_filtered:
        mep_elements = get_MEP_elements_within_bbox(level_bbox["bbox"])
        for mep_element in mep_elements:
            if mep_element.Id in [r.mep_element.Id for r in relevant_results]:
                continue

            result = get_is_mep_without_opening_intersect_with_concrete(
                mep_element, level_bounding_boxes_filtered
            )
            if result.is_intersect_with_concrete():
                relevant_results.append(result)

    if len(relevant_results) == 0:
        forms.alert("No missing openings were found.")
        return

    dialog = MepOpeningMonitorDialog(uidoc, relevant_results)
    dialog.Show()


run()
