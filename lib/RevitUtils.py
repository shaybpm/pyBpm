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

    comp_model_guids = ["e6cfe7b1-d7de-4fed-a584-b403a09e9d47"]

    def is_model_link_in_guids(link):
        doc_link = link.GetLinkDocument()
        if not doc_link:
            return False
        if not doc_link.IsModelInCloud:
            return False
        link_model_guid = doc_link.GetCloudModelPath().GetModelGUID().ToString()
        return link_model_guid in comp_model_guids

    all_links = FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()
    for link in all_links:
        if is_model_link_in_guids(link):
            return link
        if "URS" in link.Name:
            continue
        if "COMP" in link.Name or "CM" in link.Name or "BPM" in link.Name:
            return link
    return None
