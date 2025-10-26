import os, shutil
from Autodesk.Revit.DB import ElementId, Category, ViewScheduleExportOptions
from pyrevit import forms
from pyUtils import sanitize_filename
from ExcelUtils import get_excel_app_class, FIELD_DELIMITER, Excel


ex_titles = [
    "Apartment Code",
    "Building Number",
    "Level",
    "Apartment",
    "NumberRooms",
    "ApartmentNumber",
]

# Apartment Code = <Building Number>-<Level>-<Apartment>-<NumberRooms>-<ApartmentNumber>


def csv_to_excel_for_AreaDataFormatter_script(csv_path, excel_path):
    """Only for Area Data Formatter script use"""
    import os

    if not os.path.exists(csv_path):
        raise FileNotFoundError("CSV file not found: {}".format(csv_path))

    # Create a new Excel application
    excel_app = get_excel_app_class()
    workbook = excel_app.Workbooks.Add()
    worksheet = workbook.Worksheets[1]

    apartment_code_col_index = None
    building_number_col_index = None
    level_col_index = None
    apartment_col_index = None
    number_rooms_col_index = None
    apartment_number_col_index = None

    # Open the CSV file
    with open(csv_path, "r") as csv_file:
        file_obj = csv_file.read().decode("utf-8")
        rows = file_obj.split("\n")
        for row_index, row in enumerate(rows):
            columns = row.strip().split(FIELD_DELIMITER)
            for col_index, cell_value in enumerate(columns):
                cell_content = cell_value.replace('"', "")

                if (
                    apartment_code_col_index is not None
                    and apartment_code_col_index == col_index
                ):
                    if not all(
                        [
                            building_number_col_index is not None,
                            level_col_index is not None,
                            apartment_col_index is not None,
                            number_rooms_col_index is not None,
                            apartment_number_col_index is not None,
                        ]
                    ):
                        raise ValueError(
                            "One or more required columns are missing in the CSV file."
                        )

                    max_col_index = max(
                        building_number_col_index,
                        level_col_index,
                        apartment_col_index,
                        number_rooms_col_index,
                        apartment_number_col_index,
                    )
                    if max_col_index < len(columns):
                        apartment_code_value = "{}-{}-{}-{}-{}".format(
                            columns[building_number_col_index].replace('"', ""),
                            columns[level_col_index].replace('"', ""),
                            columns[apartment_col_index].replace('"', ""),
                            columns[number_rooms_col_index].replace('"', ""),
                            columns[apartment_number_col_index].replace('"', ""),
                        )
                        cell_content = apartment_code_value

                if (
                    apartment_code_col_index is None
                    and cell_content == "Apartment Code"
                ):
                    apartment_code_col_index = col_index
                elif (
                    building_number_col_index is None
                    and cell_content == "Building Number"
                ):
                    building_number_col_index = col_index
                elif level_col_index is None and cell_content == "Level":
                    level_col_index = col_index
                elif apartment_col_index is None and cell_content == "Apartment":
                    apartment_col_index = col_index
                elif number_rooms_col_index is None and cell_content == "NumberRooms":
                    number_rooms_col_index = col_index
                elif (
                    apartment_number_col_index is None
                    and cell_content == "ApartmentNumber"
                ):
                    apartment_number_col_index = col_index

                worksheet.Cells(row_index + 1, col_index + 1).Value2 = cell_content

    # Save the workbook as an Excel file
    workbook.SaveAs(excel_path, Excel.XlFileFormat.xlWorkbookDefault)
    workbook.Close()
    excel_app.Quit()


def schedules_filter(schedule):
    definition = schedule.Definition
    cat_id = definition.CategoryId
    if cat_id == ElementId.InvalidElementId:
        return False
    category = Category.GetCategory(schedule.Document, cat_id)
    if not category:
        return False
    if category.Name != "Areas":
        return False

    titles = []
    table_data = schedule.GetTableData()
    for section_index in range(table_data.NumberOfSections):
        section_data = table_data.GetSectionData(section_index)
        n_rows = section_data.NumberOfRows
        if n_rows == 0:
            return False
        n_cols = section_data.NumberOfColumns
        if n_cols == 0:
            return False

        for col in range(n_cols):
            cell_text = section_data.GetCellText(0, col)
            if not cell_text:
                continue
            titles.append(cell_text)

    for ex_title in ex_titles:
        if ex_title not in titles:
            return False

    return True


def area_data_formatter(uidoc):
    doc = uidoc.Document
    schedules = forms.select_schedules(filterfunc=schedules_filter, doc=doc)
    if not schedules:
        return

    folder = forms.pick_folder(title="Select folder to save the excel files")
    if not folder:
        return

    temp_folder = os.path.join(folder, "temp_csv_files")
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    view_schedule_export_options = ViewScheduleExportOptions()
    view_schedule_export_options.FieldDelimiter = FIELD_DELIMITER

    for schedule in schedules:
        file_name = "{}.csv".format(sanitize_filename(schedule.Name))
        csv_path = os.path.join(temp_folder, file_name)
        excel_path = os.path.join(
            folder, "{}.xlsx".format(sanitize_filename(schedule.Name))
        )
        schedule.Export(temp_folder, file_name, view_schedule_export_options)
        csv_to_excel_for_AreaDataFormatter_script(csv_path, excel_path)

    shutil.rmtree(temp_folder)

    to_open_folder = forms.alert(
        "Area Data Formatter completed successfully.\n\nDo you want to open the output folder?",
        yes=True,
        no=False,
        title="Area Data Formatter",
    )
    if to_open_folder:
        os.startfile(folder)


# --------------------------------
# OLD

# from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory, Transaction, ElementId, BuiltInParameter
# from pyrevit import forms
# from ProgressBar import ProgressBar, UserCanceledException


# def area_data_formatter(uidoc):
#     doc = uidoc.Document
#     areas = (
#         FilteredElementCollector(doc)
#         .OfCategory(BuiltInCategory.OST_Areas)
#         .WhereElementIsNotElementType()
#         .ToElements()
#     )
#     # areas = [doc.GetElement(ElementId(13459028))]  # for testing a single area
#     if not areas:
#         forms.alert("No areas found in the document.", title="Area Data Formatter")
#         return

#     target_parameter_name = "Apartment Code"

#     source1_parameter_name = "Building Number"
#     source2_b_i_parameter = BuiltInParameter.LEVEL_NAME
#     source3_parameter_name = "Apartment"
#     source4_parameter_name = "NumberRooms"

#     def ex_func(progress_bar):  # type: (ProgressBar) -> None
#         progress_bar.pre_set_main_status("{}/{}".format(0, float(len(areas))))
#         t = Transaction(doc, "pyBpm | Area Data Formatter")
#         t.Start()
#         try:
#             for i, area in enumerate(areas):
#                 param_target = area.LookupParameter(target_parameter_name)
#                 param_source1 = area.LookupParameter(source1_parameter_name)
#                 param_source2 = area.get_Parameter(source2_b_i_parameter)
#                 param_source3 = area.LookupParameter(source3_parameter_name)
#                 param_source4 = area.LookupParameter(source4_parameter_name)

#                 # if some parameter is missing, rollback and alert
#                 if not all(
#                     [
#                         param_target,
#                         param_source1,
#                         param_source2,
#                         param_source3,
#                         param_source4,
#                     ]
#                 ):
#                     t.RollBack()
#                     forms.alert(
#                         "One or more parameters are missing",
#                         title="Area Data Formatter",
#                     )
#                     return

#                 value1 = param_source1.AsValueString() or "?"
#                 value2 = param_source2.AsValueString() or "?"
#                 value3 = param_source3.AsValueString() or "?"
#                 value4 = param_source4.AsValueString() or "?"

#                 formatted_value = "{}-{}-{}-{}".format(value1, value2, value3, value4)
#                 param_target.Set(formatted_value)

#                 main_percent = (i + 1) * (100 / float(len(areas)))
#                 main_text = "{}/{}".format(i + 1, len(areas))
#                 progress_bar.update_main_status(main_percent, main_text)
#         except UserCanceledException:
#             if t.HasStarted() and not t.HasEnded():
#                 t.RollBack()
#             return
#         except Exception as ex:
#             forms.alert(str(ex), title="Error")
#         finally:
#             progress_bar.Close()

#         t.Commit()

#     ProgressBar.exec_with_progressbar(
#         ex_func, title="Area Data Formatter", cancelable=True, height=150
#     )
