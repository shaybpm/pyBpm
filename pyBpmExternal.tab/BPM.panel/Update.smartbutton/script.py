# -*- coding: utf-8 -*-
""" Update pyBpmExternal Extension. """
__title__ = 'Update'
__author__ = 'Eyal Sinay'

# ------------------------------------------------------------
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
import Update

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'lib'))
import HttpRequest
import pyUtils
# ------------------------------------------------------------

def __selfinit__(script_cmp, ui_button_cmp, __rvt__):
	try:
		github_extension_file = HttpRequest.get_request("https://raw.githubusercontent.com/shaybpm/pyBpmExternal/main/extension.json")
		last_version = github_extension_file['version']

		local_extension_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'extension.json')
		local_extension_file = pyUtils.get_json_from_file(local_extension_path)
		current_version = local_extension_file["version"]
		
		has_update_icon = script_cmp.get_bundle_file('icon_hasupdates.png')
		if last_version != current_version:
			ui_button_cmp.set_icon(has_update_icon)
		return True
	except:
		return False

if __name__ == '__main__':
    Update.run()
