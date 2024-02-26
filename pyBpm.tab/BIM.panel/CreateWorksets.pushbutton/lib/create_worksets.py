# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (
    WorksetTable,
    Workset,
    Transaction,
    TransactionGroup,
    FilteredWorksetCollector,
    WorksetKind,
)

import ExcelUtils

from pyrevit import forms, script

output = script.get_output()
output.close_others()

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document


def get_workset_names(path, discipline):
    excel_app = ExcelUtils.get_excel_app_class()
    workbook = excel_app.Workbooks.Open(path)
    worksheet_name = "ANNEXE BEP 02"
    worksheet = workbook.Worksheets[worksheet_name]
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


def get_rename_existing_dict(user_workset_names):
    rename_dict = {
        "Shared Levels and Grids": None,
        "Shared Views, Levels, Grids": None,
        "Shared Levels & Grids": None,
        "Workset1": None,
        "Workset 1": None,
    }
    new_user_workset_names = []
    for workset_name in user_workset_names:
        for key in rename_dict:
            if key in workset_name:
                rename_dict[key] = workset_name
                break
        else:
            new_user_workset_names.append(workset_name)
    return rename_dict, new_user_workset_names


def is_workset_in_use(workset_name):
    return not WorksetTable.IsWorksetNameUnique(doc, workset_name)


def rename_existing_workset(rename_dict):
    t = Transaction(doc, "BPM | Rename Worksets")
    t.Start()
    all_worksets = (
        FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset).ToWorksets()
    )
    for workset in all_worksets:
        workset_old_name = workset.Name
        if workset_old_name in rename_dict:
            workset_new_name = rename_dict[workset_old_name]
            if workset_new_name is None:
                continue
            if is_workset_in_use(workset_new_name):
                output.print_html(
                    '<div style="color:red" >Workset {} is in use. The name of the workset {} is not changed.</div>'.format(
                        workset_new_name, workset_old_name
                    )
                )
                continue
            WorksetTable.RenameWorkset(doc, workset.Id, workset_new_name)
            output.print_html(
                '<div style="color:green" >Workset {} renamed to {}</div>'.format(
                    workset_old_name, workset_new_name
                )
            )
    t.Commit()


def main(excel_path, discipline):
    if not doc.IsWorkshared:
        forms.alert("Document is not workshared")
        return

    output.print_html("<h1>Workset From Excel</h1>")
    t_group = TransactionGroup(doc, "BPM | Set BPM Worksets")
    t_group.Start()

    output.print_html(
        "<h3>Excel Path: {} | Discipline: {}</h3>".format(excel_path, discipline)
    )

    user_workset_names = get_workset_names(excel_path, discipline)

    rename_existing_dict, user_workset_names = get_rename_existing_dict(
        user_workset_names
    )
    rename_existing_workset(rename_existing_dict)

    workset_names = []
    for user_workset_name in user_workset_names:
        if is_workset_in_use(user_workset_name):
            output.print_html(
                '<div style="color:red">Workset {} is in use</div>'.format(
                    user_workset_name
                )
            )
            continue
        workset_names.append(user_workset_name)
    if len(workset_names) == 0:
        output.print_html('<div style="color:red" >No worksets to create</div>')
        t_group.Assimilate()
        return
    output.print_html("<h4>{} worksets to create:</h4>".format(len(workset_names)))
    t = Transaction(doc, "BPM | Create Worksets")
    t.Start()
    for workset_name in workset_names:
        Workset.Create(doc, workset_name)
        output.print_html(
            '<div style="color:green" >Workset {} created</div>'.format(workset_name)
        )
    t.Commit()
    t_group.Assimilate()
    output.print_html('<h4 style="margin-top:8px; color:blue">Done</h4>')
