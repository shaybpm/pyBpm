# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (
    Transaction,
    TransactionGroup,
    BoundingBoxXYZ,
    XYZ,
    CategoryType,
)

from ExEventHandlers import get_simple_external_event
from ExternalEventDataFile import ExternalEventDataFile
from RevitUtils import get_ui_view, get_bpm_3d_view, turn_of_categories


def show_opening_3d_cb(uiapp):
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

    t_group = TransactionGroup(doc, "pyBpm | Show Opening 3D")
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


show_opening_3d_event = get_simple_external_event(show_opening_3d_cb)
