import json, os, sys
from pyrevit import script
from HttpRequest import get_request
from RevitUtils import get_model_info


def get_env_mode():
    # TODO: IMPROVE!
    if "Software_Development\PyRevit\extension\pyBpm.extension" in __file__:
        return "dev"
    else:
        return "prod"


db_url = "http://localhost:5000/" if get_env_mode() == "dev" else "NOT_AVAILABLE"


def get_opening_set_temp_file_id(doc):
    OPENING_SET_TEMP_FILE_ID = "OPENING_SET"
    return OPENING_SET_TEMP_FILE_ID + "_" + doc.Title


def is_to_run_opening_set_by_hooks(doc):
    # run only for projects with specific GUIDs:
    # - Test 2023 - a6e508f0-b3be-4b30-b60e-9d49a4f6d5da
    project_guids = [
        "a6e508f0-b3be-4b30-b60e-9d49a4f6d5da",
    ]
    if not doc.IsModelInCloud:
        return False
    cloudModelPath = doc.GetCloudModelPath()
    projectGuid = cloudModelPath.GetProjectGUID().ToString()
    if projectGuid not in project_guids:
        return False
    return True


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

    def set_openings_tracking_permission(self):
        opening_tracking_permission_data = get_request(
            db_url
            + "api/openings/tracking/permission-status/"
            + self.model_info["projectGuid"]
        )
        bool_result = opening_tracking_permission_data["bool"]
        current_data = self.get_data()
        current_data["openings_tracking"] = bool_result
        with open(self.file_path, "w") as f:
            f.write(json.dumps(current_data))

    def get_openings_tracking_permission(self):
        current_data = self.get_data()
        if "openings_tracking" not in current_data:
            return None
        return current_data["openings_tracking"]

    def set_all_permissions(self):
        self.set_openings_tracking_permission()
