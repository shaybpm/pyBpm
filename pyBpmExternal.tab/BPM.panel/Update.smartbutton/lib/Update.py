# -*- coding: utf-8 -*-
""" Update pyBpmExternal Extension. """
__title__ = 'Update'
__author__ = 'Eyal Sinay'

# ------------------------------

import os, sys
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
    print("Update pyBpmExternal...")
    return

    extensions_folder = os.path.join(os.getenv('APPDATA'), 'pyRevit', 'Extensions')

    if not os.path.isdir(extensions_folder):
        print("The update failed.")
        return

    pyBpmExternal_folder = os.path.join(extensions_folder, 'pyBpmExternal.extension')

    if os.path.isdir(pyBpmExternal_folder):
        shutil.rmtree(pyBpmExternal_folder)
    else:
        print("The update failed.")
        return

    download_url = "https://github.com/shaybpm/pyBpmExternal/archive/refs/heads/main.zip"
    zip_filename = os.path.join(extensions_folder, "pyBpmExternal.zip")

    try:
        HttpRequest.download_file(download_url, zip_filename)
    except Exception as e:
        print("The installation failed. Make sure you are connected to the internet and try again.")
        print(e)
        return

    ZipFile.ExtractToDirectory(zip_filename, extensions_folder)
    zipped_folder_name = next(os.walk(extensions_folder))[1][0]
    zipped_folder = os.path.join(extensions_folder, zipped_folder_name)

    os.rename(zipped_folder, pyBpmExternal_folder)
    os.remove(zip_filename)

    print("The update was successful.")

    # Reload pyrevit:
    logger = script.get_logger()
    results = script.get_results()
    # re-load pyrevit session.
    logger.info('Reloading....')
    sessionmgr.reload_pyrevit()
    results.newsession = sessioninfo.get_session_uuid()
