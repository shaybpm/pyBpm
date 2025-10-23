from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory, Transaction, BuiltInParameter
from pyrevit import forms
from ProgressBar import ProgressBar, UserCanceledException


def area_data_formatter(uidoc):
    doc = uidoc.Document
    areas = (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Areas)
        .WhereElementIsNotElementType()
        .ToElements()
    )
    # areas = [doc.GetElement(ElementId(13459028))]  # for testing a single area
    if not areas:
        forms.alert("No areas found in the document.", title="Area Data Formatter")
        return

    target_parameter_name = "Apartment Code"

    source1_parameter_name = "Building Number"
    source2_b_i_parameter = BuiltInParameter.LEVEL_NAME
    source3_parameter_name = "Apartment"
    source4_parameter_name = "NumberRooms"

    def ex_func(progress_bar):  # type: (ProgressBar) -> None
        progress_bar.pre_set_main_status("{}/{}".format(0, float(len(areas))))
        t = Transaction(doc, "pyBpm | Area Data Formatter")
        t.Start()
        try:
            for i, area in enumerate(areas):
                param_target = area.LookupParameter(target_parameter_name)
                param_source1 = area.LookupParameter(source1_parameter_name)
                param_source2 = area.get_Parameter(source2_b_i_parameter)
                param_source3 = area.LookupParameter(source3_parameter_name)
                param_source4 = area.LookupParameter(source4_parameter_name)

                # if some parameter is missing, rollback and alert
                if not all(
                    [
                        param_target,
                        param_source1,
                        param_source2,
                        param_source3,
                        param_source4,
                    ]
                ):
                    t.RollBack()
                    forms.alert(
                        "One or more parameters are missing",
                        title="Area Data Formatter",
                    )
                    return

                value1 = param_source1.AsValueString() or "?"
                value2 = param_source2.AsValueString() or "?"
                value3 = param_source3.AsValueString() or "?"
                value4 = param_source4.AsValueString() or "?"

                formatted_value = "{}-{}-{}-{}".format(value1, value2, value3, value4)
                param_target.Set(formatted_value)

                main_percent = (i + 1) * (100 / float(len(areas)))
                main_text = "{}/{}".format(i + 1, len(areas))
                progress_bar.update_main_status(main_percent, main_text)
        except UserCanceledException:
            if t.HasStarted() and not t.HasEnded():
                t.RollBack()
            return
        except Exception as ex:
            forms.alert(str(ex), title="Error")
        finally:
            progress_bar.Close()
            
        t.Commit()

    ProgressBar.exec_with_progressbar(
        ex_func, title="Area Data Formatter", cancelable=True, height=150
    )
