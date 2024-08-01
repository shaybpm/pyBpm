# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (
    TransactionGroup,
    Transaction,
    Color,
    ElementId,
    CategoryType,
    BoundingBoxXYZ,
    XYZ,
)
from RevitUtils import (
    turn_of_categories,
    get_ogs_by_color,
    get_bpm_3d_view,
    get_ui_view,
)
from RevitUtilsOpenings import get_opening_filter, get_not_opening_filter
from ExEventHandlers import get_simple_external_event
from ExternalEventDataFile import ExternalEventDataFile


def turn_on_isolate_mode_cb(uiapp):
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document
    view = uidoc.ActiveView

    t_group = TransactionGroup(doc, "pyBpm | Turn On Isolate Mode")
    t_group.Start()

    t1 = Transaction(doc, "pyBpm | Turn On Isolate Mode")
    t1.Start()
    view.EnableTemporaryViewPropertiesMode(view.Id)
    t1.Commit()

    turn_of_categories(doc, view, CategoryType.Annotation)
    turn_of_categories(doc, view, CategoryType.Model, ["RVT Links", "Generic Models"])

    t2 = Transaction(doc, "pyBpm | Turn on Generic Models")
    t2.Start()
    cat_generic_models = doc.Settings.Categories.get_Item("Generic Models")
    view.SetCategoryHidden(cat_generic_models.Id, False)
    t2.Commit()

    opening_filter = get_opening_filter(doc)
    yellow = Color(255, 255, 0)
    ogs = get_ogs_by_color(doc, yellow)
    t3 = Transaction(doc, "pyBpm | Set Opening Filter")
    t3.Start()
    view.SetFilterOverrides(opening_filter.Id, ogs)
    t3.Commit()

    not_opening = get_not_opening_filter(doc)
    t4 = Transaction(doc, "pyBpm | Set Not Opening Filter")
    t4.Start()
    view.SetFilterVisibility(not_opening.Id, False)
    t4.Commit()

    t_group.Assimilate()


turn_on_isolate_mode_event = get_simple_external_event(turn_on_isolate_mode_cb)


def turn_off_isolate_mode_cb(uiapp):
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document
    view = uidoc.ActiveView

    t = Transaction(doc, "pyBpm | Turn Off Isolate Mode")
    t.Start()
    view.EnableTemporaryViewPropertiesMode(ElementId.InvalidElementId)
    t.Commit()


turn_off_isolate_mode_event = get_simple_external_event(turn_off_isolate_mode_cb)


def show_bbox_3d_cb(uiapp):
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document

    ex_event_file = ExternalEventDataFile(doc)
    min_max_points_dict = ex_event_file.get_key_value("min_max_points_dict")

    bbox = BoundingBoxXYZ()
    bbox.Min = XYZ(
        min(min_max_points_dict["Min"]["X"], min_max_points_dict["Max"]["X"]),
        min(min_max_points_dict["Min"]["Y"], min_max_points_dict["Max"]["Y"]),
        min(min_max_points_dict["Min"]["Z"], min_max_points_dict["Max"]["Z"]),
    )
    bbox.Max = XYZ(
        max(min_max_points_dict["Min"]["X"], min_max_points_dict["Max"]["X"]),
        max(min_max_points_dict["Min"]["Y"], min_max_points_dict["Max"]["Y"]),
        max(min_max_points_dict["Min"]["Z"], min_max_points_dict["Max"]["Z"]),
    )

    t_group = TransactionGroup(doc, "pyBpm | 3D Section Box")
    t_group.Start()

    bpm_3d_view = get_bpm_3d_view(doc)
    if not bpm_3d_view:
        t_group.RollBack()
        return

    uidoc.ActiveView = bpm_3d_view

    ui_view = get_ui_view(uidoc)
    if not ui_view:
        t_group.RollBack()
        return

    turn_of_categories(
        doc,
        bpm_3d_view,
        CategoryType.Annotation,
        except_categories=["Section Boxes"],
    )

    bbox_section_box = BoundingBoxXYZ()
    section_box_increment = 1.0
    bbox_section_box.Min = bbox.Min.Subtract(
        XYZ(section_box_increment, section_box_increment, section_box_increment)
    )
    bbox_section_box.Max = bbox.Max.Add(
        XYZ(section_box_increment, section_box_increment, section_box_increment)
    )
    t_set_section_box = Transaction(doc, "pyBpm | Set Section Box")
    t_set_section_box.Start()
    bpm_3d_view.SetSectionBox(bbox_section_box)
    t_set_section_box.Commit()

    t_group.Assimilate()

    zoom_increment = 1.6
    zoom_viewCorner1 = bbox_section_box.Min.Subtract(
        XYZ(zoom_increment, zoom_increment, zoom_increment)
    )
    zoom_viewCorner2 = bbox_section_box.Max.Add(
        XYZ(zoom_increment, zoom_increment, zoom_increment)
    )
    ui_view.ZoomAndCenterRectangle(zoom_viewCorner1, zoom_viewCorner2)


show_bbox_3d_event = get_simple_external_event(show_bbox_3d_cb)
