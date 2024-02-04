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
    from Config import get_opening_set_temp_file_id  # type: ignore
    from RevitUtils import getElementName  # type: ignore
    from ServerUtils import ServerPermissions  # type: ignore

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
    from RevitUtilsOpenings import opening_names  # type: ignore

    def filter_ids_by_elem_name(doc, elem_ids):
        if not elem_ids:
            return []
        elements = [doc.GetElement(elem_id) for elem_id in elem_ids]
        return [
            elem.Id
            for elem in elements
            if elem and getElementName(elem) in opening_names
        ]

    def run():
        doc = EXEC_PARAMS.event_args.GetDocument()
        server_permissions = ServerPermissions(doc)
        if not server_permissions.get_openings_tracking_permission():
            return

        category_filter = ElementCategoryFilter(BuiltInCategory.OST_GenericModel)
        not_type_filter = ElementIsElementTypeFilter(True)
        element_filter = LogicalAndFilter(category_filter, not_type_filter)

        added_element_ids = EXEC_PARAMS.event_args.GetAddedElementIds(element_filter)
        modified_element_ids = EXEC_PARAMS.event_args.GetModifiedElementIds(
            element_filter
        )
        deleted_element_ids = EXEC_PARAMS.event_args.GetDeletedElementIds()

        if (
            len(added_element_ids) == 0
            and len(modified_element_ids) == 0
            and len(deleted_element_ids) == 0
        ):
            return

        added_element_ids = filter_ids_by_elem_name(doc, added_element_ids)
        modified_element_ids = filter_ids_by_elem_name(doc, modified_element_ids)
        added_and_modified_element_ids = added_element_ids + modified_element_ids

        if (len(added_and_modified_element_ids) == 0) and (
            len(deleted_element_ids) == 0
        ):
            return

        opening_set_temp_file_id = get_opening_set_temp_file_id(doc)
        temp_storage = TempElementStorage(opening_set_temp_file_id)
        if len(added_and_modified_element_ids) > 0:
            temp_storage.add_elements(added_and_modified_element_ids)

        if len(deleted_element_ids) > 0:
            from ServerUtils import patch_deleted_elements  # type: ignore

            patch_deleted_elements(doc, deleted_element_ids)
            temp_storage.remove_elements(deleted_element_ids)

    run()
except Exception as ex:
    from Config import get_env_mode  # type: ignore

    if get_env_mode() == "dev":
        print(ex)
