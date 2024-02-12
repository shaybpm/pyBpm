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


PYBPM_3D_VIEW_NAME = "PYBPM-3D-VIEW"


def turn_of_categories(doc, view, category_type, except_categories=[]):
    from Autodesk.Revit.DB import Transaction

    t = Transaction(doc, "pyBpm | Turn off annotation categories")
    t.Start()
    categories = doc.Settings.Categories
    for category in categories:
        if category.CategoryType == category_type:
            if category.Name in except_categories:
                continue
            annotate_category_id = category.Id
            if view.CanCategoryBeHidden(annotate_category_id):
                view.SetCategoryHidden(annotate_category_id, True)
    t.Commit()


def create_bpm_3d_view(doc):
    from Autodesk.Revit.DB import (
        Transaction,
        View3D,
        ElementTypeGroup,
        ViewDetailLevel,
        DisplayStyle,
    )

    view_family_type_id = doc.GetDefaultElementTypeId(ElementTypeGroup.ViewType3D)
    t = Transaction(doc, "pyBpm | Create 3D View")
    t.Start()
    view = View3D.CreateIsometric(doc, view_family_type_id)
    view.Name = PYBPM_3D_VIEW_NAME
    if view.CanModifyDetailLevel():
        view.DetailLevel = ViewDetailLevel.Fine
    if view.CanModifyDisplayStyle():
        view.DisplayStyle = DisplayStyle.ShadingWithEdges
    t.Commit()
    return view


def get_bpm_3d_view(doc):
    from Autodesk.Revit.DB import FilteredElementCollector, View3D, ViewType

    views = FilteredElementCollector(doc).OfClass(View3D).ToElements()
    for view in views:
        if view.ViewType == ViewType.ThreeD and view.Name == PYBPM_3D_VIEW_NAME:
            return view
    return create_bpm_3d_view(doc)


def get_ogs_by_color(doc, color):
    from Autodesk.Revit.DB import (
        OverrideGraphicSettings,
        Color,
        FillPatternElement,
        LinePatternElement,
        FilteredElementCollector,
    )

    ogs = OverrideGraphicSettings()
    ogs.SetCutBackgroundPatternColor(color)
    ogs.SetCutForegroundPatternColor(color)
    ogs.SetCutLineColor(Color(0, 0, 0))
    ogs.SetProjectionLineColor(Color(0, 0, 0))
    ogs.SetSurfaceBackgroundPatternColor(color)
    ogs.SetSurfaceForegroundPatternColor(color)

    all_patterns = (
        FilteredElementCollector(doc).OfClass(FillPatternElement).ToElements()
    )
    solid_patterns = [i for i in all_patterns if i.GetFillPattern().IsSolidFill]
    for solid_pattern in solid_patterns:
        ogs.SetSurfaceForegroundPatternId(solid_pattern.Id)
        ogs.SetCutForegroundPatternId(solid_pattern.Id)

    line_pattern = LinePatternElement.GetLinePatternElementByName(doc, "Solid")
    if line_pattern:
        ogs.SetProjectionLinePatternId(line_pattern.Id)
        ogs.SetCutLinePatternId(line_pattern.Id)

    return ogs


def get_tags_of_element_in_view(view, element_unique_id):
    from Autodesk.Revit.DB import FilteredElementCollector, IndependentTag

    doc = view.Document
    revit_version = getRevitVersion(doc)

    tags_in_view = (
        FilteredElementCollector(view.Document, view.Id)
        .OfClass(IndependentTag)
        .ToElements()
    )

    all_links = get_all_link_instances(doc)

    def is_ref_is_the_target(ref):
        element = doc.GetElement(ref)
        if element and element.UniqueId == element_unique_id:
            return True
        linked_element_id = ref.LinkedElementId
        for link in all_links:
            doc_link = link.GetLinkDocument()
            if not doc_link:
                continue
            element = doc_link.GetElement(linked_element_id)
            if element and element.UniqueId == element_unique_id:
                return True
        return False

    elem_tags = []
    for tag in tags_in_view:
        if revit_version < 2022:
            ref = tag.GetTaggedReference()
            if ref and is_ref_is_the_target(ref):
                elem_tags.append(tag)
        else:
            refs = tag.GetTaggedReferences()
            for ref in refs:
                if is_ref_is_the_target(ref):
                    elem_tags.append(tag)
    return elem_tags


def get_element_by_unique_id(doc, unique_id):
    elem = doc.GetElement(unique_id)
    if elem:
        return elem
    all_links = get_all_link_instances(doc)
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue
        elem = link_doc.GetElement(unique_id)
        if elem:
            return elem


def get_model_guids(doc):
    model_guids = []
    doc_model_info = get_model_info(doc)
    model_guids.append(doc_model_info["modelGuid"])

    all_links = get_all_link_instances(doc)
    for link in all_links:
        link_doc = link.GetLinkDocument()
        if not link_doc:
            continue
        link_doc_model_info = get_model_info(link_doc)
        if link_doc_model_info["modelGuid"] not in model_guids:
            model_guids.append(link_doc_model_info["modelGuid"])

    return model_guids
