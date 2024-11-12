shapes = {
    "rectangular": [
        "Rectangular Face Opening",
        "REC_FLOOR OPENING",
        "REC_WALL OPENING",
    ],
    "circular": ["Round Face Opening", "CIRC_FLOOR OPENING", "CIRC_WALL OPENING"],
}
opening_names = shapes["rectangular"] + shapes["circular"]

PYBPM_FILTER_NAME_OPENING = "PYBPM-FILTER-NAME_OPENING"
PYBPM_FILTER_NAME_NOT_OPENING = "PYBPM-FILTER-NAME_NOT-OPENING"


def is_opening_rectangular(opening):
    from RevitUtils import getElementName

    opening_symbol = opening.Symbol
    opening_symbol_name = getElementName(opening_symbol)
    opening_symbol_family_name = opening_symbol.FamilyName
    return (
        "REC" in opening_symbol_name.upper()
        or "REC" in opening_symbol_family_name.upper()
    )


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
        doc, PYBPM_FILTER_NAME_OPENING, category_ids_iCollection, element_filter
    )
    t.Commit()

    return new_parameter_filter


def get_opening_filter(doc):
    from Autodesk.Revit.DB import FilteredElementCollector, ParameterFilterElement

    filters = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
    for filter in filters:
        if filter.Name == PYBPM_FILTER_NAME_OPENING:
            return filter
    return create_opening_filter(doc)


def create_not_opening_filter(doc):
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
        LogicalAndFilter,
        Category,
        ElementParameterFilter,
    )

    built_in_categories = [BuiltInCategory.OST_GenericModel]
    category_ids = [Category.GetCategory(doc, x).Id for x in built_in_categories]
    category_ids_iCollection = List[ElementId](category_ids)

    element_parameter_filter_rules = List[ElementFilter]([])
    for opening_name in opening_names:
        rule = ParameterFilterRuleFactory.CreateNotContainsRule(
            ElementId(BuiltInParameter.ALL_MODEL_TYPE_NAME),
            opening_name,
        )
        element_parameter_filter_rules.Add(ElementParameterFilter(rule))

    element_filter = LogicalAndFilter(element_parameter_filter_rules)

    t = Transaction(doc, "pyBpm | Create Not Opening Filter")
    t.Start()
    new_parameter_filter = ParameterFilterElement.Create(
        doc, PYBPM_FILTER_NAME_NOT_OPENING, category_ids_iCollection, element_filter
    )
    t.Commit()

    return new_parameter_filter


def get_not_opening_filter(doc):
    from Autodesk.Revit.DB import FilteredElementCollector, ParameterFilterElement

    filters = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
    for filter in filters:
        if filter.Name == PYBPM_FILTER_NAME_NOT_OPENING:
            return filter
    return create_not_opening_filter(doc)


def get_opening_element_filter(doc):
    """Returns a element filter for all the openings in the model."""
    import clr

    clr.AddReferenceByPartialName("System")
    from System.Collections.Generic import List

    from RevitUtils import getElementName

    from Autodesk.Revit.DB import (
        FilteredElementCollector,
        BuiltInCategory,
        FamilyInstanceFilter,
        LogicalOrFilter,
        ElementFilter,
    )

    element_filters = List[ElementFilter]()
    generic_model_types = (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_GenericModel)
        .WhereElementIsElementType()
        .ToElements()
    )
    for gmt in generic_model_types:
        if getElementName(gmt) in opening_names:
            element_filters.Add(FamilyInstanceFilter(doc, gmt.Id))
            continue
        # ~~~ Special supports ~~~
        #   ICHILOV NORTH TOWER (R22)
        #   Electronic Team
        #   Ori Sagi
        if doc.Title == "ILV-NT-SMO-BASE-E" and getElementName(gmt).startswith("MCT"):
            element_filters.Add(FamilyInstanceFilter(doc, gmt.Id))
            continue
        # ~~~ Special supports ~~~

    if element_filters.Count == 0:
        return None

    logical_or_filter = LogicalOrFilter(element_filters)
    return logical_or_filter


def get_all_openings(doc):
    """Returns a list of all the openings in the model."""
    import clr

    clr.AddReferenceByPartialName("System")
    from System.Collections.Generic import List

    from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory, Element

    opening_element_filter = get_opening_element_filter(doc)
    if not opening_element_filter:
        return List[Element]()

    return (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_GenericModel)
        .WherePasses(opening_element_filter)
        .ToElements()
    )


def get_all_openings_include_links(doc):
    """Returns a list of all the openings in the model."""
    from RevitUtils import get_all_link_instances

    all_openings = [{"elements": get_all_openings(doc), "link": None}]

    for link in get_all_link_instances(doc):
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue
        linked_openings = {
            "elements": get_all_openings(link_doc),
            "link": link,
        }
        all_openings.append(linked_openings)

    return all_openings


def get_opening_discipline_and_number(opening):
    """Returns the discipline and number of the opening."""
    from Autodesk.Revit.DB import BuiltInParameter

    return (
        opening.Symbol.get_Parameter(BuiltInParameter.ALL_MODEL_DESCRIPTION).AsString(),
        opening.get_Parameter(BuiltInParameter.ALL_MODEL_MARK).AsString(),
    )
