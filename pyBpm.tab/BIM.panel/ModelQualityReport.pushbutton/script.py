# -*- coding: utf-8 -*-
""" Open the Model Quality Report 
Click with Shift to open in browser """
__title__ = "Model Quality\nReport"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from System import Net
from System.Text import Encoding

from pyrevit import script
from RevitUtils import get_model_info
from Config import server_url
from PyRevitUtils import start_process

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

output = script.get_output()

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    model_info = get_model_info(doc)

    target_html = "{}{}/model-quality/{}?revit=true".format(
        server_url, model_info["projectGuid"], model_info["modelGuid"]
    )
    target_css = "{}styles/mq-model.css".format(server_url)

    if not __shiftclick__:  # type: ignore
        web_client = Net.WebClient()
        web_client.Encoding = Encoding.UTF8

        html = web_client.DownloadString(target_html)

        css_file = web_client.DownloadString(target_css)

        output.close_others()

        output.add_style(css_file)
        output.print_html(html)

        output.center()
        output.inject_script("window.scrollTo(0, 0);")
    else:
        path_to_open_in_browser = target_html.replace("?revit=true", "")
        start_process(path_to_open_in_browser)


run()
