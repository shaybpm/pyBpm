# -*- coding: utf-8 -*-
""" Update pyBpm Extension. """
__title__ = "Update"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
import Update  # type: ignore

root_path = __file__[: __file__.rindex(".extension") + len(".extension")]
sys.path.append(os.path.join(root_path, "lib"))
import HttpRequest  # type: ignore
import pyUtils  # type: ignore

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def __selfinit__(script_cmp, ui_button_cmp, __rvt__):
    try:
        github_extension_file = HttpRequest.get_request(
            "https://raw.githubusercontent.com/shaybpm/pyBpm/main/extension.json"
        )
        last_version = github_extension_file["version"]

        local_extension_path = os.path.join(root_path, "extension.json")
        local_extension_file = pyUtils.get_json_from_file(local_extension_path)
        current_version = local_extension_file["version"]

        has_update_icon = script_cmp.get_bundle_file("icon_hasupdates.png")
        if last_version != current_version:
            ui_button_cmp.set_icon(has_update_icon)
        return True
    except:
        return False


if __name__ == "__main__":
    env_mode = pyUtils.env_mode()
    if env_mode == "dev":
        Update.dev_run()
    else:
        Update.run()
