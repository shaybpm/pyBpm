import json, os
from pyrevit import script
from HttpRequest import get, patch, post
from RevitUtils import get_model_info, get_comp_link
from Config import server_url


class ServerPermissions:
    def __init__(self, doc):
        self.doc = doc
        self.model_info = get_model_info(doc)
        self.temp_file_id = "SERVER_PERMISSIONS" + "_" + self.model_info["modelGuid"]
        self.file_path = script.get_instance_data_file(self.temp_file_id)

    def is_file_exists(self):
        return os.path.isfile(self.file_path)

    def get_data(self):
        if not self.is_file_exists():
            return {}
        with open(self.file_path, "r") as f:
            data = f.read()
            if not data:
                return {}
            data = json.loads(data)
            return data

    def get_openings_tracking_permission(self):
        current_data = self.get_data()
        if "openings_tracking" not in current_data:
            current_data = self.set_project_permissions()
        return current_data["openings_tracking"]

    def get_opening_set_by_synch_permission(self):
        current_data = self.get_data()
        if "opening_set_by_synch" not in current_data:
            current_data = self.set_project_permissions()
        return current_data["opening_set_by_synch"]

    def set_project_permissions(self):
        project_permission_data = get(
            server_url + "api/info/permission-status/" + self.model_info["projectGuid"]
        )
        with open(self.file_path, "w") as f:
            f.write(json.dumps(project_permission_data))
        return project_permission_data


def patch_deleted_elements(doc, deleted_element_ids):
    model_info = get_model_info(doc)
    deleted_element_ids_int = [x.IntegerValue for x in deleted_element_ids]
    data = {
        "projectGuid": model_info["projectGuid"],
        "modelGuid": model_info["modelGuid"],
        "modelPathName": model_info["modelPathName"],
        "internalDocIds": deleted_element_ids_int,
    }
    patch(server_url + "api/openings/tracking/opening-deleted", data)


def get_openings_changes(doc, start_time_str, end_time_str, model_guids):
    import urllib

    start_time_str = urllib.quote_plus(start_time_str)
    end_time_str = urllib.quote_plus(end_time_str)
    model_info = get_model_info(doc)
    endpoint = "api/openings/tracking/time/{}?start={}&end={}&models={}".format(
        model_info["projectGuid"],
        start_time_str,
        end_time_str,
        ",".join(model_guids),
    )
    return get(server_url + endpoint)


def change_openings_approved_status(doc, password, newStatusArr):
    data = {
        "projectGuid": get_model_info(doc)["projectGuid"],
        "password": password,
        "newStatusArr": newStatusArr,
    }
    return patch(server_url + "api/openings/tracking/opening-approved", data)


class ProjectStructuralModels:
    def __init__(self, doc):
        self.doc = doc
        self.structural_models = self.get_structural_models()

    def set_structural_models(self, value):
        url = "{}api/projects/set-structural-models".format(server_url)
        model_info = get_model_info(self.doc)
        data = {
            "projectGuid": model_info["projectGuid"],
            "modelGuid": model_info["modelGuid"],
            "modelPathName": model_info["modelPathName"],
            "structuralModelGuids": value,
        }
        post(url, data)
        self.structural_models = value

    def get_structural_models(self):
        model_info = get_model_info(self.doc)
        url = "{}api/projects/{}".format(server_url, model_info["projectGuid"])
        try:
            data = get(url)
            more_data = data.get("moreData")
            if more_data is None:
                return []
            return more_data.get("structuralModelGuids", [])
        except Exception:
            return []


def get_model_quality_auto_checks_data(doc):
    if not doc.IsModelInCloud:
        return None
    comp_link = get_comp_link(doc)
    if not comp_link:
        return None
    comp_doc = comp_link.GetLinkDocument()

    comp_doc_model_guid = get_model_info(comp_doc)["modelGuid"]
    url = "{}api/model-quality-auto/model-guid/{}".format(
        server_url, comp_doc_model_guid
    )
    return get(url)


def get_filtered_model_quality_auto_checks(doc, filter_by_importance="A"):
    data = get_model_quality_auto_checks_data(doc)
    if not data:
        return None

    checks = data.get("data")
    if not checks:
        return None

    filter_by_importance_list = (
        ["A", "B", "C"]
        if filter_by_importance == "C"
        else ["A", "B"] if filter_by_importance == "B" else ["A"]
    )

    filtered_checks = []
    doc_model_guid = get_model_info(doc)["modelGuid"]
    for check in checks:
        if check.get("modelGuid") != doc_model_guid:
            continue
        if check.get("importanceGroup") not in filter_by_importance_list:
            continue
        filtered_checks.append(check)

    return filtered_checks


def is_model_quality_auto_checks_successful(doc, filter_by_importance="A"):
    """
    By default, return True.

    filter_by_importance: A returns only A, B returns A and B, and C returns all.
    """
    try:
        filtered_checks = get_filtered_model_quality_auto_checks(
            doc, filter_by_importance
        )
        if not filtered_checks:
            return True

        for check in filtered_checks:
            if check.get("boolResult") is False:
                return False

        return True

    except Exception:
        return True
