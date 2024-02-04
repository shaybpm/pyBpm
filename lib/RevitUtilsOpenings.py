shapes = {
    "rectangular": [
        "Rectangular Face Opening",
        "REC_FLOOR OPENING",
        "REC_WALL OPENING",
    ],
    "circular": ["Round Face Opening", "CIRC_FLOOR OPENING", "CIRC_WALL OPENING"],
}
opening_names = shapes["rectangular"] + shapes["circular"]

PYBPM_OPENING_FILTER_NAME = "PYBPM-OPENING-FILTER"


def create_opening_filter(doc):
    import clr

    clr.AddReferenceByPartialName("System")
    from System.Collections.Generic import List

    from Autodesk.Revit.DB import (
        Transaction,
        BuiltInCategory,
        BuiltInParameter,
        ParameterFilterElement,
        ElementId,
        ParameterFilterRuleFactory,
        ElementFilter,
        LogicalOrFilter,
        Category,
        ElementParameterFilter,
    )

    built_in_categories = [BuiltInCategory.OST_GenericModel]
    category_ids = [Category.GetCategory(doc, x).Id for x in built_in_categories]
    category_ids_iCollection = List[ElementId](category_ids)

    element_parameter_filter_rules = List[ElementFilter]([])
    for opening_name in opening_names:
        rule = ParameterFilterRuleFactory.CreateContainsRule(
            ElementId(BuiltInParameter.ALL_MODEL_TYPE_NAME),
            opening_name,
        )
        element_parameter_filter_rules.Add(ElementParameterFilter(rule))

    element_filter = LogicalOrFilter(element_parameter_filter_rules)

    t = Transaction(doc, "pyBpm | Create Opening Filter")
    t.Start()
    new_parameter_filter = ParameterFilterElement.Create(
        doc, PYBPM_OPENING_FILTER_NAME, category_ids_iCollection, element_filter
    )
    t.Commit()

    return new_parameter_filter


def get_opening_filter(doc):
    from Autodesk.Revit.DB import FilteredElementCollector, ParameterFilterElement

    filters = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
    for filter in filters:
        if filter.Name == PYBPM_OPENING_FILTER_NAME:
            return filter
    return create_opening_filter(doc)
