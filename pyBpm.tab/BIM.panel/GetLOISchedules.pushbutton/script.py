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
)

from pyrevit import forms

from TransferUtility import execute_function_on_cloud_doc, get_project_container_guids

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document
# selection = [doc.GetElement(x) for x in uidoc.Selection.GetElementIds()]

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def filter_schedules(schedule):
    schedule_parameter_name = "Schedule Exporter"
    parm = schedule.LookupParameter(schedule_parameter_name)
    if not parm:
        return False
    param_int_val = parm.AsInteger()
    return param_int_val == 1


def handle_active_view_want_to_be_deleted(doc, view_want_to_be_deleted_ids):
    return True


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

    # Remove Existing Schedules
    schedules_in_this_doc = (
        FilteredElementCollector(this_doc).OfClass(ViewSchedule).ToElements()
    )
    schedules_in_container_doc_names = [x.Name for x in schedules_in_container_doc]
    schedules_in_this_doc = [
        x for x in schedules_in_this_doc if x.Name in schedules_in_container_doc_names
    ]
    success = handle_active_view_want_to_be_deleted(doc, schedules_in_this_doc)
    if not success:
        forms.alert(
            "עליך להחליף את המבט הנוכחי למבט שאינו\nLOI Schedule"
        )
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
