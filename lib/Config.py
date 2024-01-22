def get_env_mode():
    if "Software_Development\PyRevit\extension\pyBpm.extension" in __file__:
        return "dev"
    else:
        return "prod"


OPENING_ST_TEMP_FILE_ID = "OPENING_ST_TEMP_FILE_ID"
