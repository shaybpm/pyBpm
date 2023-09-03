# -*- coding: utf-8 -*-
""" Update pyBpmExternal Extension. """
__title__ = 'Update'
__author__ = 'Eyal Sinay'

# ------------------------------------------------------------

import sys, os
import clr
import shutil
from pyrevit import script
from pyrevit.loader import sessionmgr
from pyrevit.loader import sessioninfo

clr.AddReference('System')
clr.AddReference('System.Net')
clr.AddReference('System.IO.Compression.FileSystem')

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'lib'))

from System.IO.Compression import ZipFile
import HttpRequest

def run():
    output = script.get_output()
    output.print_html('<h2>Update pyBpmExternal...</h2>')

    pyBpmExternal_folder_name = 'pyBpmExternal.extension'

    index_of_extension = __file__.find(pyBpmExternal_folder_name)
    extensions_folder = __file__[:index_of_extension - 1]

    if not os.path.isdir(extensions_folder):
        output.print_html('<div style="color:red;">The update failed.</div>')
        return

    pyBpmExternal_folder = os.path.join(extensions_folder, pyBpmExternal_folder_name)

    if os.path.isdir(pyBpmExternal_folder):
        shutil.rmtree(pyBpmExternal_folder)
    else:
        output.print_html('<div style="color:red;">The update failed.</div>')
        return

    download_url = "https://github.com/shaybpm/pyBpmExternal/archive/refs/heads/main.zip"
    zip_filename = os.path.join(extensions_folder, "pyBpmExternal.zip")

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

    os.rename(zipped_folder, pyBpmExternal_folder)
    os.remove(zip_filename)

    output.print_html('<div style="color:green;">The update was successful.</div>')

    # Reload pyrevit:
    logger = script.get_logger()
    results = script.get_results()
    # re-load pyrevit session.
    logger.info('Reloading....')
    sessionmgr.reload_pyrevit()
    results.newsession = sessioninfo.get_session_uuid()

def dev_run():
    output = script.get_output()
    print("dev_run")
    output.print_html('<strong>Update pyBpmExternal...</strong>')
    output.print_html('<div style="color:red;">The update failed.</div>')
    output.print_html('<div style="color:green;">The update was successful.</div>')
