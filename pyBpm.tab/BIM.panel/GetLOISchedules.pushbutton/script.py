# -*- coding: utf-8 -*-
"""Copy or update the LOI schedules from the template model."""
__title__ = "Get LOI\nSchedules"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import clr

clr.AddReferenceByPartialName("System")
from System.Collections.Generic import List
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    ViewSchedule,
    Transaction,
    ElementId,
    ElementTransformUtils,
    StartingViewSettings,
    View,
)

from pyrevit import forms

from TransferUtility import execute_function_on_cloud_doc, get_project_container_guids

import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "ui"))
from GetLOISchedulesResults import GetLOISchedulesResults # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def get_user_schedules(schedules):
    opt_dict = {}
    zz_list = []
    for schedule in schedules:
        schedule_name = schedule.Name
        if "/" not in schedule_name:
            continue
        schedule_chars = schedule_name.split("/")[0]
        if len(schedule_chars) == 0:
            continue
        if schedule_chars.upper() == "ZZ":
            zz_list.append(schedule)
            continue
        if schedule_chars not in opt_dict:
            opt_dict[schedule_chars] = []
        opt_dict[schedule_chars].append(schedule)

    options = list(opt_dict.keys())
    options.sort()
    only_zz_schedules_str = "Only ZZ Schedules"
    options.append(only_zz_schedules_str)
    selected_key = forms.SelectFromList.show(
        options, title="Select your discipline"
    )
    if not selected_key:
        return None
    if selected_key == only_zz_schedules_str:
        return zz_list
    selected_schedules = opt_dict[selected_key]
    selected_schedules.extend(zz_list)
    return selected_schedules


def filter_schedules(schedule):
    schedule_parameter_name = "Schedule Exporter"
    parm = schedule.LookupParameter(schedule_parameter_name)
    if not parm:
        return False
    param_int_val = parm.AsInteger()
    if param_int_val != 1:
        return False
    schedule_name = schedule.Name
    if "/" not in schedule_name:
        return False
    return True


def handle_active_view_want_to_be_deleted(view_want_to_be_deleted_ids):
    active_view = doc.ActiveView
    if active_view.Id not in view_want_to_be_deleted_ids:
        return True

    # Get all open views in the current document
    ui_views = uidoc.GetOpenUIViews()
    for ui_view in ui_views:
        view_id = ui_view.ViewId
        if view_id in view_want_to_be_deleted_ids:
            continue
        view = doc.GetElement(view_id)
        if view is None:
            continue
        if not isinstance(view, View):
            continue
        if view.IsTemplate:
            continue
        uidoc.ActiveView = view
        return True

    # Try to get the start view of the project
    starting_view_settings = StartingViewSettings.GetStartingViewSettings(doc)
    starting_view_id = starting_view_settings.ViewId
    if (
        starting_view_id != ElementId.InvalidElementId
        and starting_view_id not in view_want_to_be_deleted_ids
    ):
        starting_view = doc.GetElement(starting_view_id)
        if starting_view is not None:
            uidoc.ActiveView = starting_view
            return True

    return False


def cb_function(this_doc, link_doc):
    schedules_in_container_doc = (
        FilteredElementCollector(link_doc).OfClass(ViewSchedule).ToElements()
    )
    schedules_in_container_doc = [
        x for x in schedules_in_container_doc if filter_schedules(x)
    ]
    if not schedules_in_container_doc:
        forms.alert("No schedules found in the linked model.")
        return
    schedules_in_container_doc = get_user_schedules(schedules_in_container_doc)
    if not schedules_in_container_doc:
        return

    # Remove Existing Schedules
    schedules_in_this_doc = (
        FilteredElementCollector(this_doc).OfClass(ViewSchedule).ToElements()
    )
    schedules_in_container_doc_names = [x.Name for x in schedules_in_container_doc]
    schedules_in_this_doc = [
        x for x in schedules_in_this_doc if x.Name in schedules_in_container_doc_names
    ]
    success = handle_active_view_want_to_be_deleted(
        [x.Id for x in schedules_in_this_doc]
    )
    if not success:
        forms.alert("עליך להחליף את המבט הנוכחי למבט שאינו\nLOI Schedule")
        return

    if schedules_in_this_doc:
        t = Transaction(this_doc, "BPM_TEST | Remove Existing Schedules")
        t.Start()
        this_doc.Delete(List[ElementId]([x.Id for x in schedules_in_this_doc]))
        t.Commit()

    schedules_in_container_doc_ids = List[ElementId](
        [x.Id for x in schedules_in_container_doc]
    )
    t = Transaction(doc, "BPM | Copy schedules")
    t.Start()
    copied_ids = ElementTransformUtils.CopyElements(
        link_doc, schedules_in_container_doc_ids, this_doc, None, None
    )
    t.Commit()

    # Set the 'Include Linked Files' to False:
    t = Transaction(doc, "BPM_TEST | Not Include Linked Files")
    t.Start()
    for schedule_id in copied_ids:
        schedule_view = doc.GetElement(schedule_id)
        if isinstance(schedule_view, ViewSchedule):
            if schedule_view.Definition.CanIncludeLinkedFiles():
                schedule_view.Definition.IncludeLinkedFiles = False
    t.Commit()
    
    copied = []
    for schedule_id in copied_ids:
        schedule_view = doc.GetElement(schedule_id)
        if isinstance(schedule_view, ViewSchedule):
            copied.append(schedule_view)
    get_LOI_schedules_results = GetLOISchedulesResults(
        uidoc, copied
    )
    get_LOI_schedules_results.Show()


def run():
    if not doc.IsModelInCloud:
        forms.alert("This script only works with cloud models.")
        return
    project_guid, model_container_guid = get_project_container_guids(doc)
    if not project_guid or not model_container_guid:
        forms.alert("No project container found.")
        return
    execute_function_on_cloud_doc(
        uidoc,
        "US",
        project_guid,
        model_container_guid,
        cb_function,
        transaction_group_name="pyBpm | Get schedules",
        back_to_init_state=True,
    )


run()
