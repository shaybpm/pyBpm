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

    project_guid = get_model_info(doc)["projectGuid"]
    if project_guid == "bc7a92f5-0388-4436-ab65-80716234307b":  # הקו הירוק
        for link in all_links:
            link_doc = link.GetLinkDocument()
            if not link_doc:
                continue
            if "BPM-UT" in link_doc.Title:
                return link

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


def get_all_link_types(doc):
    from Autodesk.Revit.DB import FilteredElementCollector, RevitLinkType

    return FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()


def get_link_types_status(doc):
    all_link_types = get_all_link_types(doc)

    status = {}
    for link_type in all_link_types:
        link_status = link_type.GetLinkedFileStatus().ToString()
        if link_status not in status:
            status[link_status] = []
        status[link_status].append(getElementName(link_type))
    return status


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


def get_min_max_from_two_points(min_point, max_point):
    from Autodesk.Revit.DB import XYZ

    min_x = min(min_point.X, max_point.X)
    min_y = min(min_point.Y, max_point.Y)
    min_z = min(min_point.Z, max_point.Z)
    max_x = max(min_point.X, max_point.X)
    max_y = max(min_point.Y, max_point.Y)
    max_z = max(min_point.Z, max_point.Z)
    return XYZ(min_x, min_y, min_z), XYZ(max_x, max_y, max_z)


def get_min_max_points_from_bbox(bbox, transform=None):
    min_rel_to_bbox = bbox.Min
    max_rel_to_bbox = bbox.Max
    bbox_transform = bbox.Transform
    min_rel_to_document = bbox_transform.OfPoint(min_rel_to_bbox)
    max_rel_to_document = bbox_transform.OfPoint(max_rel_to_bbox)
    if not transform:
        return get_min_max_from_two_points(min_rel_to_document, max_rel_to_document)

    min_rel_to_transform = transform.OfPoint(min_rel_to_document)
    max_rel_to_transform = transform.OfPoint(max_rel_to_document)

    return get_min_max_from_two_points(min_rel_to_transform, max_rel_to_transform)


def getOutlineByBoundingBox(bbox, transform=None):
    from Autodesk.Revit.DB import Outline, XYZ, Transform

    if transform is None:
        transform = Transform.Identity

    min, max = get_min_max_points_from_bbox(bbox, transform)
    outline = Outline(min, max)
    outline.AddPoint(XYZ(min.X, min.Y, max.Z))
    outline.AddPoint(XYZ(max.X, max.Y, min.Z))
    outline.AddPoint(XYZ(min.X, max.Y, max.Z))
    outline.AddPoint(XYZ(max.X, min.Y, min.Z))
    outline.AddPoint(XYZ(max.X, min.Y, max.Z))
    outline.AddPoint(XYZ(min.X, max.Y, min.Z))
    return outline


def is_wall_concrete(wall):
    """
    This function try many checks to determine if the wall is concrete.
    Note that this is not a perfect solution, and there are many some where it will fail.
    """
    from Autodesk.Revit.DB import BuiltInParameter

    wall_doc = wall.Document

    if convertRevitNumToCm(wall_doc, wall.Width) >= 15:
        # * Don't sure if this is a good check
        return True

    doc_title = wall_doc.Title
    if "str" in doc_title.lower() or "con" in doc_title.lower():
        return True

    if "בטון" in wall.Name:
        return True
    if "con" in wall.Name.lower():
        return True
    if "str" in wall.Name.lower():
        return

    material_ids = wall.GetMaterialIds(False)
    for material_id in material_ids:
        material = wall.Document.GetElement(material_id)
        if "בטון" in material.Name:
            return True
        if "con" in material.Name.lower():
            return True
        if "str" in material.Name.lower():
            return True

    wall_structural_param = wall.get_Parameter(
        BuiltInParameter.WALL_STRUCTURAL_SIGNIFICANT
    )
    if wall_structural_param and wall_structural_param.AsInteger() == 1:
        return True

    return False


def get_levels_sorted(doc):
    from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory

    levels = (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Levels)
        .WhereElementIsNotElementType()
        .ToElements()
    )
    levels = sorted(levels, key=lambda level: level.ProjectElevation)
    return levels


def get_solid_from_geometry_element(geometry_element, transform=None):
    from Autodesk.Revit.DB import Solid, SolidUtils, Line

    for geo_instance in geometry_element:
        if isinstance(geo_instance, Line):
            continue
        if isinstance(geo_instance, Solid):
            if geo_instance.Volume > 0:
                if transform:
                    geo_instance = SolidUtils.CreateTransformed(geo_instance, transform)
                return geo_instance
            else:
                continue
        instance_geometry = geo_instance.GetInstanceGeometry()
        for geo_instance_2 in instance_geometry:
            if isinstance(geo_instance_2, Solid):
                if geo_instance_2.Volume > 0:
                    if transform:
                        geo_instance_2 = SolidUtils.CreateTransformed(
                            geo_instance_2, transform
                        )
                    return geo_instance_2


def get_solid_from_element(element, transform=None, options=None):
    from Autodesk.Revit.DB import Options

    if not options:
        options = Options()
    geometry_element = element.get_Geometry(options)
    return get_solid_from_geometry_element(geometry_element, transform)
