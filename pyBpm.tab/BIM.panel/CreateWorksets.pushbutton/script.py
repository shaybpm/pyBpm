# -*- coding: utf-8 -*-
""" Create Worksets by the BEP. """
__title__ = "Create\nWorksets"
__author__ = "BPM"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from RevitUtils import getRevitVersion
from pyrevit.forms import pick_excel_file, pick_file, SelectFromList

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
from create_worksets import main, get_discipline_list_dict_from_excel, get_discipline_list_dict_from_csv  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def print_error_message(e):
    print("An error occurred while creating the worksets.")
    print(e)
    print("-" * 50)
    print("Please check the file and try again.")


def get_discipline(discipline_list_dict):
    discipline_key = SelectFromList.show(
        discipline_list_dict.keys(),
        button_name="Select the discipline",
        title="Discipline",
    )
    if not discipline_key:
        return None
    return discipline_list_dict[discipline_key]


def run_for_2024_and_below():
    excel_path = pick_excel_file(
        title="Select the Excel file located in the BEP folder of the project."
    )
    if not excel_path:
        return

    try:
        discipline_list_dict = get_discipline_list_dict_from_excel(excel_path)
    except Exception as e:
        print_error_message(e)

    discipline = get_discipline(discipline_list_dict)
    if not discipline:
        return

    try:
        main(excel_path, "xlsx", discipline)
    except Exception as e:
        print_error_message(e)


def run_for_2025_and_above():
    csv_path = pick_file(
        file_ext="csv",
        title="Select the CSV file located in the BEP folder of the project.",
    )
    if not csv_path:
        return

    try:
        discipline_list_dict = get_discipline_list_dict_from_csv(csv_path)
    except Exception as e:
        print_error_message(e)

    discipline = get_discipline(discipline_list_dict)
    if not discipline:
        return

    try:
        main(csv_path, "csv", discipline)
    except Exception as e:
        print_error_message(e)


def run():
    revit_version = getRevitVersion(doc)
    if revit_version < 2025:
        run_for_2024_and_below()
    else:
        run_for_2025_and_above()


run()
