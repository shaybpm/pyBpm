# -*- coding: utf-8 -*-
"""description"""
__title__ = "title"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import clr
clr.AddReferenceByPartialName("System")
from System.Collections.Generic import List
from Autodesk.Revit.DB import FilteredElementCollector, ViewSchedule, Transaction, ElementId, ElementTransformUtils

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


def cb_function(this_doc, link_doc):
    schedules_in_container_doc = (
        FilteredElementCollector(link_doc).OfClass(ViewSchedule).ToElements()
    )
    schedules_in_container_doc = [x for x in schedules_in_container_doc if filter_schedules(x)]
    if not schedules_in_container_doc:
        forms.alert("No schedules found in the linked model.")
        return
    
    # Remove Existing Schedules
    schedules_in_this_doc = FilteredElementCollector(this_doc).OfClass(ViewSchedule).ToElements()
    t = Transaction(this_doc, "BPM_TEST | Remove Existing Schedules")
    t.Start()
    for schedule_in_container in schedules_in_container_doc:
        # find by name
        schedule_in_this_doc = [
            x for x in schedules_in_this_doc if x.Name == schedule_in_container.Name
        ]
        if schedule_in_this_doc:
            this_doc.Delete(schedule_in_this_doc[0].Id)
    t.Commit()
    
    schedule_ids_in_linked_doc = List[ElementId](
        [x.Id for x in schedules_in_container_doc]
    )
    t = Transaction(doc, "BPM | Copy schedules")
    t.Start()
    copied_ids = ElementTransformUtils.CopyElements(
        link_doc, schedule_ids_in_linked_doc, doc, None, None
    )
    t.Commit()
    
    # Set the 'Include Linked Files' to False:
    t = Transaction(doc, "BPM_TEST | Not Include Linked Files")
    t.Start()
    for schedule_id in copied_ids:
        schedule_view = doc.GetElement(schedule_id)
        if isinstance(schedule_view, ViewSchedule):
            schedule_view.Definition.IncludeLinkedFiles = False
    t.Commit()


def run():
    if not doc.IsModelInCloud:
        forms.alert("This script only works with cloud models.")
        return
    [project_guid, model_container_guid] = get_project_container_guids(doc)
    execute_function_on_cloud_doc(
        uidoc,
        "US",
        project_guid,
        model_container_guid,
        cb_function,
        transaction_group_name="pyBpm | Get schedules",
        back_to_init_state=False,
        uidoc=uidoc,
    )


run()
