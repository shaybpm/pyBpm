import json, os
from pyrevit import script
from HttpRequest import get
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

    def set_openings_tracking_permission(self):
        opening_tracking_permission_data = get(
            server_url
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
