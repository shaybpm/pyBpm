# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (
    BuiltInCategory,
    FilteredElementCollector,
    Transaction,
    TransactionGroup,
    ElementCategoryFilter,
    LogicalOrFilter,
    BoundingBoxIntersectsFilter,
    BoundingBoxIsInsideFilter,
    BuiltInParameter,
    Category,
)
from pyrevit import forms

from SharedParametersUtils import SharedParameterManager, PyBpmSharedParameters
from RevitUtils import getRevitVersion, getOutlineByBoundingBox
from ProgressBar import ProgressBar, UserCanceledException

from Categories import built_in_categories
from SRI_PreDialog import SRI_PreDialog


def add_the_shared_parameters_to_the_categories(app, doc):
    categories = []
    for b_i_cat in built_in_categories:
        category = Category.GetCategory(doc, b_i_cat)
        if category:
            categories.append(category)

    pyBpm_shared_parameters = PyBpmSharedParameters()
    instance_parameter_names = [
        pyBpm_shared_parameters.BPM_Room_Level.name,
        pyBpm_shared_parameters.BPM_FM_Mark.name,
        pyBpm_shared_parameters.BPM_Room_Num.name,
        pyBpm_shared_parameters.BPM_Link_Source.name,
        pyBpm_shared_parameters.BPM_Room_Name.name,
    ]
    type_parameter_names = [
        pyBpm_shared_parameters.BPM_FM_SubType.name,
        pyBpm_shared_parameters.BPM_FM_Type.name,
    ]

    sp_instance_guids = [
        PyBpmSharedParameters().get_parameter_by_name(name).guid
        for name in instance_parameter_names
    ]

    sp_type_guids = [
        PyBpmSharedParameters().get_parameter_by_name(name).guid
        for name in type_parameter_names
    ]

    with SharedParameterManager(app, doc) as sp_manager:
        sp_manager.add_shared_parameters_to_categories(
            sp_instance_guids, categories, type_binding=False
        )
        sp_manager.add_shared_parameters_to_categories(
            sp_type_guids, categories, type_binding=True
        )


def get_parameters_from_element(element, param_names):
    name_param_dict = {}
    pyBpm_shared_parameters = PyBpmSharedParameters()
    for param_name in param_names:
        py_bpm_shared_param = pyBpm_shared_parameters.get_parameter_by_name(param_name)
        if not py_bpm_shared_param:
            raise ValueError(
                "Shared parameter '{}' not found in PyBpmSharedParameters.".format(
                    param_name
                )
            )
        param = element.get_Parameter(py_bpm_shared_param.guid)
        if not param:
            raise ValueError(
                "Could not retrieve parameter '{}' after adding it. element: {}".format(
                    param_name, element.Id
                )
            )
        name_param_dict[param_name] = param
    return name_param_dict


def ask_for_source_models(doc):
    dialog = SRI_PreDialog(doc)
    dialog.ShowDialog()
    return dialog.sources_link_result


def get_elements(doc):
    cat_element_filters = [
        ElementCategoryFilter(b_i_cat) for b_i_cat in built_in_categories
    ]
    logical_or_categories = LogicalOrFilter(cat_element_filters)

    return (
        FilteredElementCollector(doc)
        .WherePasses(logical_or_categories)
        .WhereElementIsNotElementType()
        .ToElements()
    )


def main(app, doc):
    revit_version = getRevitVersion(doc)
    if revit_version < 2023:
        forms.alert(
            "This script requires Revit 2023 or later.",
        )
        return

    if not doc.IsModelInCloud:
        return

    source_links = ask_for_source_models(doc)
    if not source_links:
        return

    def ex_func(progress_bar):  # type: (ProgressBar) -> None

        elements = get_elements(doc)

        if len(elements) == 0:
            return

        progress_bar.pre_set_main_status(
            "{}/{}".format(0, len(elements))
        )

        t_group = TransactionGroup(doc, "pyBpm | Sync Room Info")
        t_group.Start()

        t = None
        try:
            add_the_shared_parameters_to_the_categories(app, doc)

            pyBpm_shared_parameters = PyBpmSharedParameters()
            for i, elem in enumerate(elements):

                param_new_values = {
                    pyBpm_shared_parameters.BPM_Room_Num.name: {
                        "parameter": None,
                        "new_value": "",
                        "cb_func": lambda room: room.Number,
                    },
                    pyBpm_shared_parameters.BPM_Room_Level.name: {
                        "parameter": None,
                        "new_value": "",
                        "cb_func": lambda room: room.Level.Name if room.Level else "-",
                    },
                    pyBpm_shared_parameters.BPM_Room_Name.name: {
                        "parameter": None,
                        "new_value": "",
                        "cb_func": lambda room: room.get_Parameter(
                            BuiltInParameter.ROOM_NAME
                        ).AsString(),
                    },
                    pyBpm_shared_parameters.BPM_Link_Source.name: {
                        "parameter": None,
                        "new_value": "",
                        "cb_func": lambda room: room.Document.Title,
                    },
                }

                name_param_dict = get_parameters_from_element(
                    elem, param_new_values.keys()
                )
                for param_name, param_info in param_new_values.items():
                    param_info["parameter"] = name_param_dict[param_name]

                for link in source_links:
                    link_doc = link.GetLinkDocument()
                    if not link_doc:
                        continue

                    elem_bbox = elem.get_BoundingBox(None)
                    if not elem_bbox:
                        continue
                    outline = getOutlineByBoundingBox(
                        elem_bbox, link.GetTotalTransform().Inverse
                    )
                    bbox_intersect_filter = BoundingBoxIntersectsFilter(outline)
                    bbox_inside_filter = BoundingBoxIsInsideFilter(outline)
                    bbox_filter = LogicalOrFilter(
                        bbox_intersect_filter, bbox_inside_filter
                    )

                    room = (
                        FilteredElementCollector(link_doc)
                        .OfCategory(BuiltInCategory.OST_Rooms)
                        .WherePasses(bbox_filter)
                        .WhereElementIsNotElementType()
                        .FirstElement()
                    )
                    if not room:
                        continue

                    t = Transaction(doc, "pyBpm | Sync Room Info")
                    t.Start()
                    for param_name, param_info in param_new_values.items():
                        param = param_info["parameter"]
                        new_value = param_info["cb_func"](room)
                        if new_value is not None:
                            param.Set(new_value)
                    t.Commit()
                    break

                main_percent = (i + 1) * (100 / float(len(elements)))
                main_text = "{}/{}".format(i + 1, len(elements))
                progress_bar.update_main_status(main_percent, main_text)

            t_group.Assimilate()

        except UserCanceledException:
            if t is not None and t.HasStarted() and not t.HasEnded():
                t.RollBack()
            if t_group.HasStarted() and not t_group.HasEnded():
                t_group.RollBack()
        except Exception as ex:
            forms.alert(str(ex), title="Error")
        finally:
            progress_bar.Close()

    ProgressBar.exec_with_progressbar(
        ex_func,
        title="Sync Room Info",
        cancelable=True,
        height=200,
    )
