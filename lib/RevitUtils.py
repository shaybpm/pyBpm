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


def get_model_info(doc):
    if not doc.IsModelInCloud:
        raise Exception("Model is not in cloud")
    pathName = doc.PathName
    splitPathName = pathName.split("/")
    projectName = splitPathName[len(splitPathName) - 2]
    modelName = doc.Title  # splitPathName[len(splitPathName) - 1]
    cloudModelPath = doc.GetCloudModelPath()
    projectGuid = cloudModelPath.GetProjectGUID().ToString()
    modelGuid = cloudModelPath.GetModelGUID().ToString()
    return {
        "projectName": projectName,
        "modelName": modelName,
        "projectGuid": projectGuid,
        "modelGuid": modelGuid,
        "modelPathName": pathName,
    }


def get_ui_view(uidoc):
    doc = uidoc.Document
    ui_views = uidoc.GetOpenUIViews()
    for ui_view in ui_views:
        if ui_view.ViewId == doc.ActiveView.Id:
            return ui_view
    return None


def get_all_link_instances(doc):
    from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory

    return (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_RvtLinks)
        .WhereElementIsNotElementType()
        .ToElements()
    )


def get_link_by_model_guid(doc, model_guid):
    all_links = get_all_link_instances(doc)
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue
        link_info = get_model_info(link_doc)
        if link_info["modelGuid"] == model_guid:
            return link
    return None


def get_transform_by_model_guid(doc, model_guid):
    from Autodesk.Revit.DB import Transform

    model_info = get_model_info(doc)
    if model_info["modelGuid"] == model_guid:
        return Transform.Identity

    link = get_link_by_model_guid(doc, model_guid)
    if not link:
        return None
    return link.GetTotalTransform()
