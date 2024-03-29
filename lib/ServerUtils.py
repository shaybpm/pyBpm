import json, os
from pyrevit import script
from HttpRequest import get, patch
from RevitUtils import get_model_info
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
