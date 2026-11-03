# -*- coding: utf-8 -*-
__title__ = "Update"
__author__ = "Eyal Sinay"
__doc__ = """Downloads and installs the latest pyBpm version, then reloads pyRevit.
The icon changes when an update is available.

Press F1 for a detailed explanation in Hebrew."""
__helpurl__ = "https://pybpm.azurewebsites.net/tutorials/pybpm-extension-update"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import Update  # type: ignore

import Config
import PyBpmAppUtils

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def __selfinit__(script_cmp, ui_button_cmp, __rvt__):
    try:
        has_update_icon = script_cmp.get_bundle_file("icon_hasupdates.png")
        if PyBpmAppUtils.has_new_version():
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
