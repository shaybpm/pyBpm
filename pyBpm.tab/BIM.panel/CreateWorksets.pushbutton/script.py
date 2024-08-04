# -*- coding: utf-8 -*-
""" Create Worksets by the BEP. """
__title__ = "Create\nWorksets"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from pyrevit.forms import pick_excel_file, SelectFromList

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
from create_worksets import main  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    excel_path = pick_excel_file(
        title="Select the Excel file located in the BEP folder of the project."
    )
    if not excel_path:
        return

    discipline_list_dict = {
        "ARCHITECTURE": "A",
        "STRUCTURE": "S",
        "HVAC": "H",
        "PLUMBING": "P",
        "ELECTRICITY": "E",
        "KITCHEN": "K",
        "LANDSCAPE": "L",
        "COORDINATION": "CM",
    }
    discipline_key = SelectFromList.show(
        discipline_list_dict.keys(),
        button_name="Select the discipline",
        title="Discipline",
    )
    if not discipline_key:
        return
    discipline = discipline_list_dict[discipline_key]

    try:
        main(excel_path, discipline)
    except Exception as e:
        print("An error occurred while creating the worksets.")
        print(e)
        print("-" * 50)
        print("Please check the Excel file and try again.")


run()
