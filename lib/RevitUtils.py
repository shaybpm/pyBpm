# -*- coding: utf-8 -*-
uiapp = __revit__  # type: ignore
uidoc = uiapp.ActiveUIDocument
if uidoc:
    doc = uiapp.ActiveUIDocument.Document

revit_version = int(doc.Application.VersionNumber)


def getElementName(element):
    from Autodesk.Revit.DB import Element

    return Element.Name.__get__(element)


def convertRevitNumToCm(num):
    from Autodesk.Revit.DB import UnitUtils

    if revit_version < 2021:
        from Autodesk.Revit.DB import DisplayUnitType

        return UnitUtils.ConvertFromInternalUnits(num, DisplayUnitType.DUT_CENTIMETERS)
    else:
        from Autodesk.Revit.DB import UnitTypeId

        return UnitUtils.ConvertFromInternalUnits(num, UnitTypeId.Centimeters)


def convertCmToRevitNum(cm):
    from Autodesk.Revit.DB import UnitUtils

    if revit_version < 2021:
        from Autodesk.Revit.DB import DisplayUnitType

        return UnitUtils.ConvertToInternalUnits(cm, DisplayUnitType.DUT_CENTIMETERS)
    else:
        from Autodesk.Revit.DB import UnitTypeId

        return UnitUtils.ConvertToInternalUnits(cm, UnitTypeId.Centimeters)


def get_comp_link(doc):
    from Autodesk.Revit.DB import FilteredElementCollector, RevitLinkInstance

    all_links = FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()
    for link in all_links:
        if "URS" in link.Name:
            continue
        if "COMP" in link.Name or "CM" in link.Name or "BPM" in link.Name:
            return link
    return None
