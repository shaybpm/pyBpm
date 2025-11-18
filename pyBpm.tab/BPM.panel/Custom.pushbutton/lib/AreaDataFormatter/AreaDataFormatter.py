# -*- coding: utf-8 -*-

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
    "Name",
    "LookUpCode",
]

# Apartment Code = <Building Number>-<Level>-<Apartment>-<NumberRooms>-<ApartmentNumber>


def get_worksheet_name_by_csv_path(csv_path, exist_names):
    _name = os.path.basename(csv_path)
    _name = os.path.splitext(_name)[0]
    _name = sanitize_filename(_name)
    _name = _name[:31]  # Excel worksheet name max length is 31 characters
    original_name = _name
    i = 1
    while _name in exist_names:
        suffix = "_{}".format(i)
        if len(original_name) + len(suffix) > 31:
            _name = original_name[: 31 - len(suffix)] + suffix
        else:
            _name = original_name + suffix
        i += 1
    return _name


def csv_to_excel_for_AreaDataFormatter_script(csv_paths, excel_path):
    """Only for Area Data Formatter script use"""
    import os

    def _ensure_required_columns(indices):
        """Verify all required columns exist; raise if not."""
        if any(idx is None for idx in indices):
            raise ValueError(
                "One or more required columns are missing in the CSV file."
            )
        return max(indices)

    def _build_composite_value(columns, indices):
        """Build a dash-separated composite value from given column indices."""
        return "-".join(columns[idx].replace('"', "") for idx in indices)

    def str_compare(str1, str2):
        str1_without_bom = str1.encode("utf-8").decode("utf-8-sig")
        str2_without_bom = str2.encode("utf-8").decode("utf-8-sig")
        return (
            str1_without_bom is not None
            and str2_without_bom is not None
            and str1_without_bom.strip().lower() == str2_without_bom.strip().lower()
        )

    # Create a new Excel application
    excel_app = get_excel_app_class()
    workbook = excel_app.Workbooks.Add()

    exist_names = []

    for index, csv_path in enumerate(csv_paths):
        if not os.path.exists(csv_path):
            raise FileNotFoundError("CSV file not found: {}".format(csv_path))

        # Choose / create worksheet
        if index == 0:
            worksheet = workbook.Worksheets[1]
        else:
            worksheet = workbook.Worksheets.Add()

        worksheet.Name = get_worksheet_name_by_csv_path(
            csv_path, exist_names
        ) or "Sheet{}".format(index + 1)
        exist_names.append(worksheet.Name)

        # Track all relevant column indices in one place
        col_indexes = {
            "apartment_code": None,
            "lookup_code": None,
            "name": None,
            "building_number": None,
            "level": None,
            "apartment": None,
            "number_rooms": None,
            "apartment_number": None,
        }

        # Open the CSV file
        with open(csv_path, "r") as csv_file:
            file_obj = csv_file.read().decode("utf-8")
            rows = file_obj.split("\n")

            for row_index, row in enumerate(rows):
                if not row:
                    continue  # skip empty lines

                columns = row.strip().split(FIELD_DELIMITER)

                for col_index, cell_value in enumerate(columns):
                    cell_content = cell_value.replace('"', "")

                    # --- Composite value logic (uses indices if already detected) ---

                    # Apartment Code: Building Number - Level - Apartment - NumberRooms - ApartmentNumber
                    if (
                        col_indexes["apartment_code"] is not None
                        and col_indexes["apartment_code"] == col_index
                    ):
                        required_indices = [
                            col_indexes["building_number"],
                            col_indexes["level"],
                            col_indexes["apartment"],
                            col_indexes["number_rooms"],
                            col_indexes["apartment_number"],
                        ]
                        max_col_index = _ensure_required_columns(required_indices)

                        if max_col_index < len(columns):
                            cell_content = _build_composite_value(
                                columns, required_indices
                            )
                        else:
                            raise ValueError(
                                "Something went wrong while building 'Apartment Code' composite value."
                            )

                    # LookUpCode: Building Number - Level - Apartment - NumberRooms - ApartmentNumber - Name
                    elif (
                        col_indexes["lookup_code"] is not None
                        and col_indexes["lookup_code"] == col_index
                    ):
                        required_indices = [
                            col_indexes["building_number"],
                            col_indexes["level"],
                            col_indexes["apartment"],
                            col_indexes["number_rooms"],
                            col_indexes["apartment_number"],
                            col_indexes["name"],
                        ]
                        max_col_index = _ensure_required_columns(required_indices)

                        if max_col_index < len(columns):
                            cell_content = _build_composite_value(
                                columns, required_indices
                            )
                        else:
                            raise ValueError(
                                "Something went wrong while building 'LookUpCode' composite value."
                            )

                    # --- Header detection (set indices once) ---

                    if str_compare(cell_content, "Apartment Code"):
                        col_indexes["apartment_code"] = col_index
                    elif str_compare(cell_content, "LookUpCode"):
                        col_indexes["lookup_code"] = col_index
                    elif str_compare(cell_content, "Name"):
                        col_indexes["name"] = col_index
                    elif str_compare(cell_content, "Building Number"):
                        col_indexes["building_number"] = col_index
                    elif str_compare(cell_content, "Level"):
                        col_indexes["level"] = col_index
                    elif str_compare(cell_content, "Apartment"):
                        col_indexes["apartment"] = col_index
                    elif str_compare(cell_content, "NumberRooms"):
                        col_indexes["number_rooms"] = col_index
                    elif str_compare(cell_content, "ApartmentNumber"):
                        col_indexes["apartment_number"] = col_index

                    # Write to Excel
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

    csv_paths = []
    for schedule in schedules:
        file_name = "{}.csv".format(sanitize_filename(schedule.Name))
        csv_path = os.path.join(temp_folder, file_name)
        schedule.Export(temp_folder, file_name, view_schedule_export_options)
        csv_paths.append(csv_path)

    excel_path = os.path.join(
        folder,
        "{}.xlsx".format(
            sanitize_filename("Area Data Formatter - {}".format(doc.Title))
        ),
    )
    csv_to_excel_for_AreaDataFormatter_script(csv_paths, excel_path)

    shutil.rmtree(temp_folder)

    to_open_folder = forms.alert(
        "Area Data Formatter completed successfully.\n\nDo you want to open the output folder?",
        yes=True,
        no=True,
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
