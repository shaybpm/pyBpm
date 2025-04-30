# -*- coding: utf-8 -*-
from System import Guid
from Autodesk.Revit.DB import (
    RevitLinkInstance,
    Transaction,
    TransactionGroup,
    ModelPathUtils,
    RevitLinkType,
    RevitLinkOptions,
    LinkedFileStatus,
    ElementId,
)
from RevitUtils import get_doc_by_model_guid_and_uidoc, get_model_info


def load_model_from_cloud(
    doc, cloud_region, project_guid, model_guid, reload_if_loaded=False
):
    """
    Returns two values:
    1. ElementId of the top level link
    2. What was done: "CREATED" | "LOADED_FOR_USER" | "LOADED_FOR_ALL_USER" | "NOTHING | "RELOADED" | "NOTHING"
    """
    revit_cloud_region = None
    if cloud_region == "EMEA":
        revit_cloud_region = ModelPathUtils.CloudRegionEMEA
    elif cloud_region == "US":
        revit_cloud_region = ModelPathUtils.CloudRegionUS
    else:
        raise ValueError("Invalid cloud region")

    model_path = ModelPathUtils.ConvertCloudGUIDsToCloudPath(
        revit_cloud_region, Guid(project_guid), Guid(model_guid)
    )

    top_level_link_id = RevitLinkType.GetTopLevelLink(doc, model_path)
    if top_level_link_id == ElementId.InvalidElementId:
        options = RevitLinkOptions(False)
        t = Transaction(doc, "BPM | Load Revit Link")
        t.Start()
        results = RevitLinkType.Create(doc, model_path, options)
        t.Commit()
        return results.ElementId, "CREATED"

    if not RevitLinkType.IsLoaded(doc, top_level_link_id):
        revit_link_type = doc.GetElement(top_level_link_id)
        init_status = revit_link_type.GetLinkedFileStatus()
        revit_link_type.Load()
        return top_level_link_id, (
            "LOADED_FOR_USER"
            if init_status == LinkedFileStatus.LocallyUnloaded
            else "LOADED_FOR_ALL_USER"
        )

    if reload_if_loaded:
        revit_link_type = doc.GetElement(top_level_link_id)
        revit_link_type.Reload()
        return top_level_link_id, "RELOADED"

    return top_level_link_id, "NOTHING"


def execute_function_on_cloud_doc(
    uidoc, cloud_region, project_guid, model_guid, func, **kwargs
):
    """
    This function will load the model from the cloud, execute the function on the linked model and then delete or unload the link.
    This function will start a new transaction group and the func will be executed inside it.

    Arguments:
    uidoc: UIDocument;
    cloud_region: "EMEA" | "US";
    project_guid: str;
    model_guid: str;
    func: function;
    **kwargs:
        transaction_group_name: str; default: "BPM | Execute on Cloud Doc";
        back_to_init_state: bool; default: True;
    """
    doc = uidoc.Document
    # ----- STEP 1 - START - Load model from cloud -----
    revit_link_type_id, what_was_done = load_model_from_cloud(
        doc, cloud_region, project_guid, model_guid
    )

    t_group = TransactionGroup(
        doc, kwargs.get("transaction_group_name", "BPM | Execute on Cloud Doc")
    )
    t_group.Start()

    link_doc = get_doc_by_model_guid_and_uidoc(uidoc, model_guid)

    if not link_doc:
        return False

    # ----- STEP 2 - EXECUTE - Get schedules from linked model -----
    func(doc, link_doc)

    # ----- STEP 3 - END - Delete the link if it was created or unload if it was loaded -----
    if kwargs.get("back_to_init_state", True):
        if what_was_done == "CREATED":
            t2 = Transaction(doc, "BPM | Delete Revit Link Type")
            t2.Start()
            doc.Delete(revit_link_type_id)
            t2.Commit()

        t_group.Assimilate()

        if what_was_done == "LOADED_FOR_USER":
            revit_link_type = doc.GetElement(revit_link_type_id)
            revit_link_type.UnloadLocally(None)
        elif what_was_done == "LOADED_FOR_ALL_USER":
            revit_link_type = doc.GetElement(revit_link_type_id)
            revit_link_type.Unload(None)
        return True

    t_group.Assimilate()
    return True


def get_project_container_guids(doc):
    if not doc.IsModelInCloud:
        return None, None
    model_info = get_model_info(doc)
    project_guid = model_info["projectGuid"]

    model_containers_dict = {
        # {"ProjectGuid": "ModelGuid"}
        "57008003-fd42-407e-b2b9-e6516dfb9891": "9ed764e2-0ec7-4a64-b0a5-2edf4b1e48d4",
        "a6e508f0-b3be-4b30-b60e-9d49a4f6d5da": "ccbb6a82-9517-4f37-923c-110f8e115793",
    }

    model_container_guid = model_containers_dict.get(project_guid, None)
    if not model_container_guid:
        return None, None

    return project_guid, model_container_guid
