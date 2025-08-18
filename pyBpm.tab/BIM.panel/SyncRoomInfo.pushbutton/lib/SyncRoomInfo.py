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
)
from pyrevit import forms

from SharedParametersUtils import SharedParameterManager, PyBpmSharedParameters
from RevitUtils import getRevitVersion, getOutlineByBoundingBox

from Categories import built_in_categories
from SRI_PreDialog import SRI_PreDialog

def add_parameters_if_not_exists(element):
    for py_bpm_sp in PyBpmSharedParameters.to_list_static():
        sp_guid = py_bpm_sp.guid
        # TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO

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


def main(doc):
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

    elements = get_elements(doc)

    t_group = TransactionGroup(doc, "pyBpm | Sync Room Info")
    t_group.Start()

    with forms.ProgressBar(title="Element: {value} of {max_value}") as pb:
        for i, elem in enumerate(elements):
            pb.update_progress(i, len(elements))
            
            add_parameters_if_not_exists(elem)
            
            for link in source_links:
                link_doc = link.GetLinkDocument()
                if not link_doc:
                    continue

                outline = getOutlineByBoundingBox(
                    elem, link.GetTotalTransform().Inverse()
                )
                bbox_intersect_filter = BoundingBoxIntersectsFilter(outline)
                bbox_inside_filter = BoundingBoxIsInsideFilter(outline)
                bbox_filter = LogicalOrFilter(bbox_intersect_filter, bbox_inside_filter)

                room = (
                    FilteredElementCollector(link_doc)
                    .OfCategory(BuiltInCategory.OST_Rooms)
                    .WherePasses(bbox_filter)
                    .WhereElementIsNotElementType()
                    .FirstElement()
                )
                
                # TODO TODO TODO TODO TODO TODO TODO TODO

    t_group.Assimilate()
