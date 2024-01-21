# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import BuiltInCategory, ElementCategoryFilter

from pyrevit import EXEC_PARAMS


def filter_ids_by_elem_name(elem_ids):
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

    doc = EXEC_PARAMS.event_args.GetDocument()

    return [
        elem_id for elem_id in elem_ids if doc.GetElement(elem_id).Name in opening_names
    ]


def run():
    element_filter = ElementCategoryFilter(BuiltInCategory.OST_GenericModel)

    added_elements = EXEC_PARAMS.event_args.GetAddedElementIds(element_filter)
    deleted_elements = EXEC_PARAMS.event_args.GetDeletedElementIds()
    modified_elements = EXEC_PARAMS.event_args.GetModifiedElementIds(element_filter)

    if (
        len(added_elements) == 0
        and len(deleted_elements) == 0
        and len(modified_elements) == 0
    ):
        return

    added_elements = filter_ids_by_elem_name(added_elements)
    deleted_elements = filter_ids_by_elem_name(deleted_elements)
    modified_elements = filter_ids_by_elem_name(modified_elements)

    if (
        len(added_elements) == 0
        and len(deleted_elements) == 0
        and len(modified_elements) == 0
    ):
        return

    print("Added elements: {}".format(added_elements))
    print("Deleted elements: {}".format(deleted_elements))
    print("Modified elements: {}".format(modified_elements))


run()
