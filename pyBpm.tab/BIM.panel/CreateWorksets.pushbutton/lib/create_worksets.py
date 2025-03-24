# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (
    WorksetTable,
    Workset,
    Transaction,
    TransactionGroup,
    FilteredWorksetCollector,
    WorksetKind,
)

import csv
from HtmlUtils import HtmlUtils

from pyrevit import forms, script

output = script.get_output()
output.close_others()

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

html_utils = HtmlUtils()


def get_worksheet(workbook):
    worksheet_name_options = ["ANNEXE BEP", "ANNEXE BEP 02"]
    for worksheet_name in worksheet_name_options:
        worksheet = workbook.Worksheets[worksheet_name]
        if worksheet:
            return worksheet, worksheet_name
    return None, None


def get_discipline_list_dict_from_excel(excel_path):
    import ExcelUtils
    excel_app = ExcelUtils.get_excel_app_class()
    workbook = excel_app.Workbooks.Open(excel_path)
    # The titles is a ro with one value in column A.
    # The firs title is in row 6.
    # discipline_list_dict dict will be with the title as a key and the value is the first value in column A in the next row.
    worksheet, worksheet_name = get_worksheet(workbook)
    if not worksheet:
        raise ValueError(
            "Worksheet {} not found in the Excel file.".format(worksheet_name)
        )

    discipline_list_dict = {}
    START_FROM_ROW = 6
    for row in range(START_FROM_ROW, worksheet.UsedRange.Rows.Count + 1):
        cell_a = worksheet.Range["A" + str(row)]
        cell_b = worksheet.Range["B" + str(row)]
        if not cell_a.Value2 and not cell_b.Value2:
            break
        if cell_a.Value2 and not cell_b.Value2:
            discipline_list_dict[cell_a.Value2] = worksheet.Range[
                "A" + str(row + 1)
            ].Value2

    workbook.Close()
    excel_app.Quit()
    return discipline_list_dict

def get_discipline_list_dict_from_csv(csv_path):
    discipline_list_dict = {}
    START_FROM_ROW = 5
    with open(csv_path, "r") as file:
        csv_reader = csv.reader(file)
        rows = list(csv_reader)
        for i in range(START_FROM_ROW, len(rows)):
            if i + 1 >= len(rows):
                break
            row = rows[i]
            value_a = row[0]
            value_b = row[1]
            if value_a and not value_b:
                discipline_list_dict[value_a] = rows[i + 1][0]
    return discipline_list_dict

def get_workset_names_from_excel(path, discipline):
    import ExcelUtils
    excel_app = ExcelUtils.get_excel_app_class()
    workbook = excel_app.Workbooks.Open(path)
    worksheet, worksheet_name = get_worksheet(workbook)
    if not worksheet:
        raise ValueError(
            "Worksheet {} not found in the Excel file.".format(worksheet_name)
        )
    workset_names = []
    for row in range(1, worksheet.UsedRange.Rows.Count + 1):
        cell = worksheet.Range["A" + str(row)]
        if cell.Value2 == discipline:
            workset_names.append(worksheet.Range["F" + str(row)].Value2)
    workbook.Close()
    excel_app.Quit()
    return [x for x in workset_names if x is not None]

def get_workset_names_from_csv(path, discipline):
    workset_names = []
    with open(path, "r") as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if row[0] == discipline:
                workset_names.append(row[5])
    return [x for x in workset_names if x is not None]


def get_rename_dict_list(user_workset_names):
    rename_dict_list = [
        {
            "options": [
                "Shared Levels and Grids".lower(),
                "Shared_Levels_and_Grids".lower(),
                "Shared_Levels_Grids".lower(),
                "Shared Views, Levels, Grids".lower(),
                "Shared Levels & Grids".lower(),
            ],
            "rename_to": None,
        },
        {
            "options": ["Workset1".lower(), "Workset 1".lower(), "Workset_1".lower()],
            "rename_to": None,
        },
    ]

    new_user_workset_names = []

    def get_rename_to(user_workset_name, item):
        user_workset_name_lower = user_workset_name.lower()
        options = item["options"]

        for option in options:
            if option in user_workset_name_lower:
                return user_workset_name

        return None

    for user_workset_name in user_workset_names:
        for item in rename_dict_list:
            rename_to = get_rename_to(user_workset_name, item)
            if rename_to:
                item["rename_to"] = user_workset_name
                break
        else:
            new_user_workset_names.append(user_workset_name)

    return rename_dict_list, new_user_workset_names


def is_workset_in_use(workset_name):
    return not WorksetTable.IsWorksetNameUnique(doc, workset_name)


def rename_existing_workset(rename_dict_list):
    t = Transaction(doc, "BPM | Rename Worksets")
    t.Start()
    all_worksets = (
        FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset).ToWorksets()
    )
    for workset in all_worksets:
        workset_old_name = workset.Name
        for item in rename_dict_list:
            if workset_old_name.lower() in item["options"]:
                workset_new_name = item["rename_to"]
                if workset_new_name is None:
                    html_utils.add_html(
                        '<div style="color:red" >Workset {} is in "None". The name of the workset {} is not changed.</div>'.format(
                            workset_old_name, workset_old_name
                        )
                    )
                    continue
                if is_workset_in_use(workset_new_name):
                    html_utils.add_html(
                        '<div style="color:red" >Workset {} is in use. The name of the workset {} is not changed.</div>'.format(
                            workset_new_name, workset_old_name
                        )
                    )
                    continue
                WorksetTable.RenameWorkset(doc, workset.Id, workset_new_name)
                html_utils.add_html(
                    '<div style="color:green" >Workset {} renamed to {}</div>'.format(
                        workset_old_name, workset_new_name
                    )
                )
    t.Commit()


def main(file_path, file_format, discipline):
    if file_format not in ["xlsx", "csv"]:
        raise ValueError("File format must be xlsx or csv")
    
    if not doc.IsWorkshared:
        forms.alert("Document is not workshared")
        return

    html_utils.add_html("<h1>Create Worksets</h1>")
    t_group = TransactionGroup(doc, "BPM | Set BPM Worksets")
    t_group.Start()

    html_utils.add_html(
        "<h3>File Path: {} | Discipline: {}</h3>".format(file_path, discipline)
    )

    user_workset_names = (
        get_workset_names_from_excel(file_path, discipline)
        if file_format == "xlsx"
        else get_workset_names_from_csv(file_path, discipline)
    )

    rename_dict_list, user_workset_names = get_rename_dict_list(user_workset_names)
    rename_existing_workset(rename_dict_list)

    workset_names = []
    for user_workset_name in user_workset_names:
        if is_workset_in_use(user_workset_name):
            html_utils.add_html(
                '<div style="color:red">Workset {} is in use</div>'.format(
                    user_workset_name
                )
            )
            continue
        workset_names.append(user_workset_name)
    if len(workset_names) == 0:
        html_utils.add_break()
        html_utils.add_html('<div style="color:red" >No worksets to create</div>')
        t_group.Assimilate()
        output.print_html(html_utils.get_html())
        return
    html_utils.add_html("<h4>{} worksets to create:</h4>".format(len(workset_names)))
    t = Transaction(doc, "BPM | Create Worksets")
    t.Start()
    for workset_name in workset_names:
        Workset.Create(doc, workset_name)
        html_utils.add_html(
            '<div style="color:green" >Workset {} created</div>'.format(workset_name)
        )
    t.Commit()
    t_group.Assimilate()
    html_utils.add_break()
    html_utils.add_html('<h4 style="margin-top:8px; color:blue">Done</h4>')
    output.print_html(html_utils.get_html())
