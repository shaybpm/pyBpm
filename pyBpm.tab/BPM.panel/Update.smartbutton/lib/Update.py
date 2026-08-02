# -*- coding: utf-8 -*-
""" Update pyBpm Extension. """
__title__ = "Update"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import sys, os
import clr
import json
import shutil
from pyrevit import script
from pyrevit.loader import sessionmgr
from pyrevit.loader import sessioninfo

clr.AddReference("System")
clr.AddReference("System.Net")
clr.AddReference("System.IO.Compression.FileSystem")

from System.IO.Compression import ZipFile
import HttpRequest

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------

output = script.get_output()
output.close_others()

DOWNLOAD_URL = "https://github.com/shaybpm/pyBpm/archive/refs/heads/main.zip"
DOWNLOAD_ATTEMPTS = 3


def _report_failure(do_not_print, reason):
    if do_not_print:
        return
    output.print_html('<div style="color:red;">The update failed.</div>')
    print(reason)


def _remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def _cleanup_silently(paths):
    for path in paths:
        try:
            _remove_path(path)
        except Exception:
            pass


def run(do_not_print=False, do_not_reload=False):
    # Last line of defense: never overwrite a dev working tree, regardless
    # of which caller forgot to check the env mode first.
    # Lazy import - both entry points (script.py, app-init hook) have the
    # extension lib on sys.path by the time run() is called.
    import Config

    if Config.get_env_mode() == "dev":
        if not do_not_print:
            print("Dev environment detected - update is disabled.")
        return

    if not do_not_print:
        output.print_html("<h2>Update pyBpm...</h2>")

    pyBpm_folder_name = "pyBpm.extension"

    index_of_extension = __file__.find(pyBpm_folder_name)
    extensions_folder = __file__[: index_of_extension - 1]

    if not os.path.isdir(extensions_folder):
        _report_failure(
            do_not_print,
            "Extensions folder not found: {}".format(extensions_folder),
        )
        return

    pyBpm_folder = os.path.join(extensions_folder, pyBpm_folder_name)

    if not os.path.isdir(pyBpm_folder):
        _report_failure(
            do_not_print,
            "pyBpm folder not found: {}".format(pyBpm_folder),
        )
        return

    zip_filename = os.path.join(extensions_folder, "pyBpm.zip")
    staging_folder = os.path.join(extensions_folder, "pyBpm_update_staging")
    # The backup name must NOT end with ".extension", so pyRevit never loads it.
    backup_folder = os.path.join(extensions_folder, pyBpm_folder_name + ".bak")

    # The current extension stays untouched until the swap below, so any
    # failure up to that point simply aborts the update.
    try:
        _remove_path(zip_filename)
        _remove_path(staging_folder)
        _remove_path(backup_folder)
    except Exception as ex:
        _report_failure(
            do_not_print,
            "Could not clean leftovers of a previous update: {}".format(ex),
        )
        return

    last_error = None
    for _ in range(DOWNLOAD_ATTEMPTS):
        try:
            HttpRequest.download_file(DOWNLOAD_URL, zip_filename)
            last_error = None
            break
        except Exception as ex:
            last_error = ex
    if last_error is not None:
        _cleanup_silently([zip_filename])
        _report_failure(do_not_print, "Download failed: {}".format(last_error))
        if not do_not_print:
            print("Make sure you are connected to the internet and try again.")
        return

    try:
        ZipFile.ExtractToDirectory(zip_filename, staging_folder)
        sub_folder_names = next(os.walk(staging_folder))[1]
        if len(sub_folder_names) != 1:
            raise Exception(
                "Unexpected zip content: {} root folders".format(len(sub_folder_names))
            )
        new_folder = os.path.join(staging_folder, sub_folder_names[0])
        extension_json_path = os.path.join(new_folder, "extension.json")
        with open(extension_json_path, "r") as f:
            json.load(f)
    except Exception as ex:
        _cleanup_silently([zip_filename, staging_folder])
        _report_failure(do_not_print, "Extract or validation failed: {}".format(ex))
        return

    # Swap. os.rename of a folder with a locked file fails atomically,
    # leaving the current extension intact (unlike a partial rmtree).
    try:
        os.rename(pyBpm_folder, backup_folder)
    except Exception as ex:
        _cleanup_silently([zip_filename, staging_folder])
        _report_failure(
            do_not_print,
            "The extension folder is in use: {}".format(ex),
        )
        if not do_not_print:
            print("Close other Revit windows and try again.")
        return

    try:
        os.rename(new_folder, pyBpm_folder)
    except Exception as ex:
        try:
            os.rename(backup_folder, pyBpm_folder)
        except Exception as rollback_ex:
            _report_failure(
                do_not_print,
                "Rollback failed, reinstall pyBpm with the installer: {}".format(
                    rollback_ex
                ),
            )
            return
        _cleanup_silently([zip_filename, staging_folder])
        _report_failure(do_not_print, "Could not install the new version: {}".format(ex))
        return

    # Leftovers that survive this cleanup are removed at the start of the next run.
    _cleanup_silently([zip_filename, staging_folder, backup_folder])

    if not do_not_print:
        output.print_html('<div style="color:green;">The update was successful.</div>')

    if do_not_reload:
        return

    # Reload pyrevit:
    logger = script.get_logger()
    results = script.get_results()
    # re-load pyrevit session.
    logger.info("Reloading....")
    sessionmgr.reload_pyrevit()
    results.newsession = sessioninfo.get_session_uuid()


def dev_run():
    print("dev_run")
    output.print_html("<strong>Update pyBpm...</strong>")
    output.print_html('<div style="color:red;">The update failed.</div>')
    output.print_html('<div style="color:green;">The update was successful.</div>')
