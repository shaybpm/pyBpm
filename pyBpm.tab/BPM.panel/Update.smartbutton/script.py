# -*- coding: utf-8 -*-
""" Update pyBpm Extension. """
__title__ = "Update"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import os

import Update  # type: ignore

import HttpRequest
import pyUtils
import Config

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def __selfinit__(script_cmp, ui_button_cmp, __rvt__):
    try:
        github_extension_file = HttpRequest.get(
            "https://raw.githubusercontent.com/shaybpm/pyBpm/main/extension.json"
        )
        last_version = github_extension_file["version"]

        local_extension_path = os.path.join(Config.root_path, "extension.json")
        local_extension_file = pyUtils.get_json_from_file(local_extension_path)
        current_version = local_extension_file["version"]

        has_update_icon = script_cmp.get_bundle_file("icon_hasupdates.png")
        if last_version != current_version:
            ui_button_cmp.set_icon(has_update_icon, icon_size=32)
        return True
    except:
        return False


if __name__ == "__main__":
    env_mode = Config.get_env_mode()
    if env_mode == "dev":
        Update.dev_run()
    else:
        Update.run()
