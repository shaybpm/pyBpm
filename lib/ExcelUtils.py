""" ExcelUtils.py """

import clr

clr.AddReference("Microsoft.Office.Interop.Excel")
from Microsoft.Office.Interop import Excel  # type: ignore


def get_excel_app_class():
    excel = Excel.ApplicationClass()
    excel.Visible = False
    excel.DisplayAlerts = False
    return excel


def create_new_workbook_file(path):
    excel = get_excel_app_class()
    workbook = excel.Workbooks.Add()
    workbook.SaveAs(path)
    workbook.Close()
    excel.Quit()
    return path


def add_data_to_worksheet(path, data_dict_list, ignore_fields=[]):
    if not data_dict_list:
        raise ValueError("data_dict_list is empty")

    excel = get_excel_app_class()
    workbook = excel.Workbooks.Open(path)
    worksheet = workbook.Worksheets[1]

    titles = list(data_dict_list[0].keys())
    for i, title in enumerate(titles):
        if title in ignore_fields:
            continue
        worksheet.Cells[1, i + 1] = title

    for i, data_dict in enumerate(data_dict_list):
        for j, title in enumerate(titles):
            if title in ignore_fields:
                continue
            worksheet.Cells[i + 2, j + 1] = str(data_dict[title])

    workbook.Save()
    workbook.Close()
    excel.Quit()
    return path
