# -*- coding: utf-8 -*-
try:
    from Autodesk.Revit.DB import (
        BuiltInCategory,
        ElementCategoryFilter,
        ElementIsElementTypeFilter,
        LogicalAndFilter,
    )

    from pyrevit import EXEC_PARAMS

    from PyRevitUtils import TempElementStorage  # type: ignore
    from Config import get_opening_set_temp_file_id, is_to_run_opening_set_by_hooks  # type: ignore
    from RevitUtils import getElementName  # type: ignore

    def filter_ids_by_elem_name(doc, elem_ids):
        import sys, os

        sys.path.append(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "pyBpm.tab",
                "Openings.panel",
                "OpeningSet.pushbutton",
                "lib",
            )
        )
        from OpeningSet import opening_names  # type: ignore

        elements = [doc.GetElement(elem_id) for elem_id in elem_ids]

        return [
            elem.Id
            for elem in elements
            if elem and getElementName(elem) in opening_names
        ]

    def run():
        doc = EXEC_PARAMS.event_args.GetDocument()
        if not is_to_run_opening_set_by_hooks(doc):
            return

        category_filter = ElementCategoryFilter(BuiltInCategory.OST_GenericModel)
        not_type_filter = ElementIsElementTypeFilter(True)
        element_filter = LogicalAndFilter(category_filter, not_type_filter)

        added_elements = EXEC_PARAMS.event_args.GetAddedElementIds(element_filter)
        deleted_elements = EXEC_PARAMS.event_args.GetDeletedElementIds()
        modified_elements = EXEC_PARAMS.event_args.GetModifiedElementIds(element_filter)

        if (
            len(added_elements) == 0
            and len(deleted_elements) == 0
            and len(modified_elements) == 0
        ):
            return

        added_elements = filter_ids_by_elem_name(doc, added_elements)
        modified_elements = filter_ids_by_elem_name(doc, modified_elements)
        added_and_modified_elements = added_elements + modified_elements
        deleted_elements = filter_ids_by_elem_name(doc, deleted_elements)

        if (len(added_and_modified_elements) == 0) and (len(deleted_elements) == 0):
            return

        opening_set_temp_file_id = get_opening_set_temp_file_id(doc)
        temp_storage = TempElementStorage(opening_set_temp_file_id)
        if len(added_and_modified_elements) > 0:
            temp_storage.add_elements(added_and_modified_elements)

        if len(deleted_elements) > 0:
            temp_storage.remove_elements(deleted_elements)

    run()
except Exception as ex:
    from Config import get_env_mode  # type: ignore

    if get_env_mode() == "dev":
        print(ex)
