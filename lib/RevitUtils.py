# -*- coding: utf-8 -*-


def getRevitVersion(doc):
    return int(doc.Application.VersionNumber)


def getElementName(element):
    from Autodesk.Revit.DB import Element

    return Element.Name.__get__(element)


def convertRevitNumToCm(doc, num):
    from Autodesk.Revit.DB import UnitUtils

    if getRevitVersion(doc) < 2021:
        from Autodesk.Revit.DB import DisplayUnitType

        return UnitUtils.ConvertFromInternalUnits(num, DisplayUnitType.DUT_CENTIMETERS)
    else:
        from Autodesk.Revit.DB import UnitTypeId

        return UnitUtils.ConvertFromInternalUnits(num, UnitTypeId.Centimeters)


def convertCmToRevitNum(doc, cm):
    from Autodesk.Revit.DB import UnitUtils

    if getRevitVersion(doc) < 2021:
        from Autodesk.Revit.DB import DisplayUnitType

        return UnitUtils.ConvertToInternalUnits(cm, DisplayUnitType.DUT_CENTIMETERS)
    else:
        from Autodesk.Revit.DB import UnitTypeId

        return UnitUtils.ConvertToInternalUnits(cm, UnitTypeId.Centimeters)


def get_comp_link(doc):
    from Autodesk.Revit.DB import (
        BuiltInParameter,
        FilteredElementCollector,
        RevitLinkInstance,
    )

    all_links = FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue
        project_info = link_doc.ProjectInformation
        organization_name_param = project_info.get_Parameter(
            BuiltInParameter.PROJECT_ORGANIZATION_NAME
        )
        organization_description_param = project_info.get_Parameter(
            BuiltInParameter.PROJECT_ORGANIZATION_DESCRIPTION
        )
        if (
            not organization_name_param
            or not organization_name_param.AsString()
            or not organization_description_param
            or not organization_description_param.AsString()
        ):
            continue

        if (
            organization_name_param.AsString() == "BPM"
            and organization_description_param.AsString() == "CM"
        ):
            return link
    return None
