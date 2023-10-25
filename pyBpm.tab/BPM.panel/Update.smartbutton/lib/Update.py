# -*- coding: utf-8 -*-
""" Update pyBpm Extension. """
__title__ = "Update"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import sys, os
import clr
import shutil
from pyrevit import script
from pyrevit.loader import sessionmgr
from pyrevit.loader import sessioninfo

clr.AddReference("System")
clr.AddReference("System.Net")
clr.AddReference("System.IO.Compression.FileSystem")

root_path = __file__[: __file__.rindex(".extension") + len(".extension")]
sys.path.append(os.path.join(root_path, "lib"))

from System.IO.Compression import ZipFile
import HttpRequest  # type: ignore

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    output = script.get_output()
    output.print_html("<h2>Update pyBpm...</h2>")

    pyBpm_folder_name = "pyBpm.extension"

    index_of_extension = __file__.find(pyBpm_folder_name)
    extensions_folder = __file__[: index_of_extension - 1]

    if not os.path.isdir(extensions_folder):
        output.print_html('<div style="color:red;">The update failed.</div>')
        return

    pyBpm_folder = os.path.join(extensions_folder, pyBpm_folder_name)

    if not os.path.isdir(pyBpm_folder):
        output.print_html('<div style="color:red;">The update failed.</div>')
        return

    # TODO: check if the folder or some sub folder or file are in use
    shutil.rmtree(pyBpm_folder)

    download_url = "https://github.com/shaybpm/pyBpm/archive/refs/heads/main.zip"
    zip_filename = os.path.join(extensions_folder, "pyBpm.zip")

    try:
        HttpRequest.download_file(download_url, zip_filename)
    except Exception as e:
        output.print_html('<div style="color:red;">The update failed.</div>')
        print("Make sure you are connected to the internet and try again.")
        # print(e)
        return

    ZipFile.ExtractToDirectory(zip_filename, extensions_folder)
    zipped_folder_name = next(os.walk(extensions_folder))[1][0]
    zipped_folder = os.path.join(extensions_folder, zipped_folder_name)

    os.rename(zipped_folder, pyBpm_folder)
    os.remove(zip_filename)

    output.print_html('<div style="color:green;">The update was successful.</div>')

    # Reload pyrevit:
    logger = script.get_logger()
    results = script.get_results()
    # re-load pyrevit session.
    logger.info("Reloading....")
    sessionmgr.reload_pyrevit()
    results.newsession = sessioninfo.get_session_uuid()


def dev_run():
    output = script.get_output()
    print("dev_run")
    output.print_html("<strong>Update pyBpm...</strong>")
    output.print_html('<div style="color:red;">The update failed.</div>')
    output.print_html('<div style="color:green;">The update was successful.</div>')
