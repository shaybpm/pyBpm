# -*- coding: utf-8 -*-

def get_env_mode():
    # return "prod" # uncomment this line to force production mode
    # TODO: IMPROVE!
    if "C:\Users\אייל סיני\BPM LTD 102181204\BPM - Status - General\Software_Development" in __file__:
        return "dev"
    else:
        return "prod"


server_url = (
    "http://localhost:5000/"
    if get_env_mode() == "dev"
    else "https://pybpm.azurewebsites.net/"
)

extension_json_url = (
    "https://raw.githubusercontent.com/shaybpm/pyBpm/main/extension.json"
)

root_path = __file__[: __file__.rindex(".extension") + len(".extension")]


def get_opening_set_temp_file_id(doc):
    OPENING_SET_TEMP_FILE_ID = "OPENING_SET"
    return OPENING_SET_TEMP_FILE_ID + "_" + doc.Title


def get_current_version():
    import os
    import pyUtils

    local_extension_path = os.path.join(root_path, "extension.json")
    local_extension_file = pyUtils.get_json_from_file(local_extension_path)
    current_version = local_extension_file["version"]
    return current_version
