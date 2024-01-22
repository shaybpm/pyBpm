def get_env_mode():
    if "Software_Development\PyRevit\extension\pyBpm.extension" in __file__:
        return "dev"
    else:
        return "prod"


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
