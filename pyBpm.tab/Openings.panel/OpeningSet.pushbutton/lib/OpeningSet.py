# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    BuiltInCategory,
    BuiltInParameter,
    ElementId,
    BasePoint,
)

import os, sys

root_path = __file__[: __file__.rindex(".extension") + len(".extension")]
sys.path.append(os.path.join(root_path, "lib"))
import pyUtils  # type: ignore
import RevitUtils  # type: ignore

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------

opening_names = [
    "Round Face Opening",
    "Rectangular Face Opening",
    "CIRC_FLOOR OPENING",
    "CIRC_WALL OPENING",
    "REC_FLOOR OPENING",
    "REC_WALL OPENING",
]


def get_all_openings(doc):
    """Returns a list of all the openings in the model."""
    openings = []
    generic_models = (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_GenericModel)
        .WhereElementIsNotElementType()
        .ToElements()
    )
    for gm in generic_models:
        if gm.Name in opening_names:
            openings.append(gm)
            continue
        # ~~~ Special supports ~~~
        #   ICHILOV NORTH TOWER (R22)
        #   Electronic Team
        #   Ori Sagi
        if doc.Title == "ILV-NT-SMO-BASE-E" and gm.Name.startswith("MCT"):
            openings.append(gm)
            continue
        # ~~~ Special supports ~~~
    return openings


def is_floor(opening):
    """Returns True if the host of the opening is a floor, else returns False.
    We don't use the host property because sometimes the connection between the opening and the host is broken.
    """
    param__Elevation_from_Level = opening.LookupParameter("Elevation from Level")
    if not param__Elevation_from_Level:
        return False
    if param__Elevation_from_Level.IsReadOnly:
        return True
    else:
        return False


def set_mep_not_required_param(doc, opening):
    """Get the schedule level parameter and check if it is match to the opening instance in the model. If it is, set the MEP - Not Required parameter to true, else set it to false."""
    results = {
        "function": "set_mep_not_required_param",
        "status": "OK",
        "message": "",
        "opening_id": opening.Id,
    }
    param__mep_not_required = opening.LookupParameter("MEP - Not Required")
    if not param__mep_not_required:
        results["status"] = "WARNING"
        results["message"] = "No MEP - Not Required parameter found."
        return results
    if param__mep_not_required.IsReadOnly:
        results["status"] = "WARNING"
        results["message"] = "MEP - Not Required parameter is read only."
        return results
    param__schedule_level = opening.get_Parameter(
        BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM
    )
    id__schedule_level = param__schedule_level.AsElementId()
    if id__schedule_level == ElementId.InvalidElementId:
        param__mep_not_required.Set(0)
        results["status"] = "WARNING"
        results["message"] = "Schedule Level is not set."
        return results

    all_levels = (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Levels)
        .WhereElementIsNotElementType()
        .ToElements()
    )
    all_levels = [
        level for level in all_levels if level.Id != ElementId.InvalidElementId
    ]
    all_levels = sorted(all_levels, key=lambda level: level.ProjectElevation)
    if not is_floor(opening):
        all_levels_filtered = [
            level
            for level in all_levels
            if level.ProjectElevation <= opening.Location.Point.Z
        ]
        min_level = min(all_levels, key=lambda level: level.ProjectElevation)
        all_levels = (
            all_levels_filtered if len(all_levels_filtered) > 0 else [min_level]
        )
    if len(all_levels) == 0:
        param__mep_not_required.Set(0)
        results["status"] = "WARNING"
        results["message"] = "No levels found."
        return results
    target_level = all_levels[0]
    for level in all_levels:
        if abs(level.ProjectElevation - opening.Location.Point.Z) < abs(
            target_level.ProjectElevation - opening.Location.Point.Z
        ):
            target_level = level

    if target_level.Id == id__schedule_level:
        param__mep_not_required.Set(1)
        results["message"] = "MEP - Not Required parameter set to true."
        return results
    else:
        param__mep_not_required.Set(0)
        results["message"] = "MEP - Not Required parameter set to false."
        return results


def set_comments(opening):
    """Sets the comments parameter to 'F' if the host of the opening is a floor, and 'nF' if not."""
    results = {
        "function": "set_comments",
        "status": "OK",
        "message": "",
        "opening_id": opening.Id,
    }
    para__comments = opening.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
    if not para__comments:
        results["status"] = "WARNING"
        results["message"] = "No Comments parameter found."
        return results
    if para__comments.IsReadOnly:
        results["status"] = "WARNING"
        results["message"] = "Comments parameter is read only."
        return results

    if is_floor(opening):
        para__comments.Set("F")
        results["message"] = "Comments parameter set to F."
        return results
    else:
        para__comments.Set("nF")
        results["message"] = "Comments parameter set to nF."
        return results


def set_elevation_params(doc, opening):
    """Sets the elevation parameters: 'Opening Elevation' and 'Opening Absolute Level'..."""
    results = {
        "function": "set_elevation_params",
        "status": "OK",
        "message": "",
        "opening_id": opening.Id,
    }
    project_base_point = BasePoint.GetProjectBasePoint(doc)
    project_base_point_position = project_base_point.Position.Z

    survey_point = BasePoint.GetSurveyPoint(doc)
    survey_point_position = survey_point.Position.Z

    opening_location_point_z = opening.Location.Point.Z

    param__opening_elevation = opening.LookupParameter("Opening Elevation")
    param__opening_absolute_level = opening.LookupParameter("Opening Absolute Level")
    if not param__opening_elevation or not param__opening_absolute_level:
        results["status"] = "WARNING"
        results[
            "message"
        ] = "No Opening Elevation or Opening Absolute Level parameter found."
        return results
    if param__opening_elevation.IsReadOnly or param__opening_absolute_level.IsReadOnly:
        results["status"] = "WARNING"
        results[
            "message"
        ] = "Opening Elevation or Opening Absolute Level parameter is read only."
        return results
    param__opening_elevation.Set(opening_location_point_z - project_base_point_position)
    param__opening_absolute_level.Set(opening_location_point_z - survey_point_position)
    results["message"] = "Opening Elevation and Opening Absolute Level parameters set."
    return results


def set_ref_level_and_mid_elevation(opening):
    """Sets the parameter '##Reference Level' to get the value in that in the parameter 'Schedule Level', and the parameter '##Middle Elevation' to get the value that in the parameter: 'Elevation from Level'"""
    results = {
        "function": "set_ref_level_and_mid_elevation",
        "status": "OK",
        "message": "",
        "opening_id": opening.Id,
    }
    param__schedule_level = opening.get_Parameter(
        BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM
    )
    param__reference_level = opening.LookupParameter("##Reference Level")
    param__elevation_from_level = opening.LookupParameter("Elevation from Level")
    param__middle_elevation = opening.LookupParameter("##Middle Elevation")
    if (
        not param__schedule_level
        or not param__reference_level
        or not param__elevation_from_level
        or not param__middle_elevation
    ):
        results["status"] = "WARNING"
        results[
            "message"
        ] = "No Schedule Level or ##Reference Level or Elevation from Level or ##Middle Elevation parameter found."
        return results
    if param__reference_level.IsReadOnly or param__middle_elevation.IsReadOnly:
        results["status"] = "WARNING"
        results[
            "message"
        ] = "Schedule Level or ##Reference Level or Elevation from Level or ##Middle Elevation parameter is read only."
        return results
    param__reference_level.Set(param__schedule_level.AsValueString())
    param__middle_elevation.Set(param__elevation_from_level.AsDouble())
    results["message"] = "##Reference Level and ##Middle Elevation parameters set."
    return results


def is_positioned_correctly(opening):
    """Sets the parameter 'Insertion Configuration' to 'OK' if the opening is positioned correctly, else sets it to 'NOT-OK'.
    This function needs to run only if the opening is not a floor opening or a round face opening.
    """
    results = {
        "function": "is_positioned_correctly",
        "status": "OK",
        "message": "",
        "opening_id": opening.Id,
    }

    param__insertion_configuration = opening.LookupParameter("Insertion Configuration")
    if not param__insertion_configuration:
        results["status"] = "WARNING"
        results["message"] = "No Insertion Configuration parameter found."
        return results
    if param__insertion_configuration.IsReadOnly:
        results["status"] = "WARNING"
        results["message"] = "Insertion Configuration parameter is read only."
        return results

    opening_symbol = opening.Symbol
    opening_symbol_name = RevitUtils.getElementName(opening_symbol)
    opening_symbol_family_name = opening_symbol.FamilyName
    if (
        "ROUND" in opening_symbol_name.upper()
        or "CIRC" in opening_symbol_name.upper()
        or "ROUND" in opening_symbol_family_name.upper()
        or "CIRC" in opening_symbol_family_name.upper()
    ):
        param__insertion_configuration.Set("OK")
        results["message"] = "Round Face Opening. Insertion Configuration set to OK."
        return results
    if is_floor(opening):
        param__insertion_configuration.Set("OK")
        results["message"] = "Floor Opening. Insertion Configuration set to OK."
        return results

    param__h = opening.LookupParameter("h")
    if not param__h:
        results["status"] = "WARNING"
        results["message"] = "No h parameter found."
        return results

    param__cut_offset = opening.LookupParameter("Cut Offset")
    param__additional_top_cut_offset = opening.LookupParameter(
        "Additional Top Cut Offset"
    )
    param__additional_bottom_cut_offset = opening.LookupParameter(
        "Additional Bottom Cut Offset"
    )

    if (
        not param__cut_offset
        or not param__additional_top_cut_offset
        or not param__additional_bottom_cut_offset
    ):
        results["status"] = "WARNING"
        results[
            "message"
        ] = "No Cut Offset or Additional Top Cut Offset or Additional Bottom Cut Offset parameter found."
        return results

    bbox = opening.get_BoundingBox(None)
    h_num = (
        param__h.AsDouble()
        + 2 * param__cut_offset.AsDouble()
        + param__additional_top_cut_offset.AsDouble()
        + param__additional_bottom_cut_offset.AsDouble()
    )
    bb_num = bbox.Max.Z - bbox.Min.Z
    if pyUtils.is_close(h_num, bb_num, 0.001):
        param__insertion_configuration.Set("OK")
        results[
            "message"
        ] = "The position is correct. Insertion Configuration set to OK."
        return results
    else:
        param__insertion_configuration.Set("NOT-OK")
        results["status"] = "WARNING"
        results[
            "message"
        ] = "The position is not correct. Insertion Configuration set to NOT-OK. You can fix it by selecting the opening and press spacebar."
        return results


def opening_number_generator(doc):
    """Generates a number for the opening."""
    all_openings = get_all_openings(doc)
    all_existing_numbers = []
    for opening in all_openings:
        param__mark = opening.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)
        if param__mark.AsString() and param__mark.AsString().isdigit():
            all_existing_numbers.append(int(param__mark.AsString()))

    number = 1
    loop_count = 0
    max_loop_count = 3000
    while number in all_existing_numbers:
        if loop_count > max_loop_count:
            raise Exception("Opening number generator loop count exceeded.")
        loop_count += 1
        number += 1
    return str(number)


def set_mark(doc, opening):
    """Sets the Mark parameter to opening number."""
    results = {
        "function": "set_mark",
        "status": "OK",
        "message": "",
        "opening_id": opening.Id,
    }
    param__mark = opening.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)
    if not param__mark:
        results["status"] = "WARNING"
        results["message"] = "No Mark parameter found."
        return results
    if param__mark.IsReadOnly:
        results["status"] = "WARNING"
        results["message"] = "Mark parameter is read only."
        return results
    if param__mark.AsString() and param__mark.AsString().isdigit():
        results["message"] = "Mark parameter already set."
        return results
    num = opening_number_generator(doc)
    param__mark.Set(num)
    results["message"] = "Mark parameter set to {}.".format(num)
    return results


def is_workset_correct(doc, opening):
    """Checks if the opening is in the correct workset."""
    results = {
        "function": "is_workset_correct",
        "status": "OK",
        "message": "",
        "opening_id": opening.Id,
    }
    workset_id = opening.WorksetId
    if not workset_id:
        results["status"] = "WARNING"
        results["message"] = "No workset found."
        return results
    workset = doc.GetWorksetTable().GetWorkset(workset_id)
    if not workset:
        results["status"] = "WARNING"
        results["message"] = "No workset found."
        return results
    if "OPENING" in workset.Name.upper():
        results["message"] = 'Workset name includes "opening".'
        return results
    else:
        results["status"] = "WARNING"
        results["message"] = 'Workset name does not include "opening".'
        return results


def execute_all_functions(doc, opening):
    """Executes all the functions in this script."""
    results = {
        "function": "execute_all_functions",
        "status": "OK",
        "message": "",
        "opening_id": opening.Id,
        "all_results": [],
    }
    results0 = set_mep_not_required_param(doc, opening)
    results1 = set_comments(opening)
    results2 = set_elevation_params(doc, opening)
    results3 = set_ref_level_and_mid_elevation(opening)
    results4 = is_positioned_correctly(opening)
    results5 = set_mark(doc, opening)
    results6 = is_workset_correct(doc, opening)

    all_results = [results0, results1, results2, results3, results4, results5, results6]
    results["all_results"] = all_results
    is_any_warning = "WARNING" in [result["status"] for result in all_results]

    if is_any_warning:
        results["status"] = "WARNING"
        results["message"] = "Completed with warnings."
    else:
        results["message"] = "Completed successfully."
    return results
