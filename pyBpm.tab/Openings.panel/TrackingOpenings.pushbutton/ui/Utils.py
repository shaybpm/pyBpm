# -*- coding: utf-8 -*-

import clr

clr.AddReferenceByPartialName("System")
from System import DateTime

from Autodesk.Revit.DB import (
    TransactionGroup,
    Transaction,
    Curve,
    XYZ,
    Line,
    SetComparisonResult,
    RevisionCloud,
    Revision,
    CategoryType,
    Color,
    BoundingBoxXYZ,
    ElementId,
    FilteredElementCollector,
    ViewSheet,
)

from System.Collections.Generic import List

from pyrevit import forms

from RevitUtils import convertRevitNumToCm, get_ui_view as ru_get_ui_doc, get_transform_by_model_guid, get_bpm_3d_view, turn_of_categories, get_ogs_by_color, get_comp_link  # type: ignore

from RevitUtilsOpenings import get_opening_filter, get_not_opening_filter  # type: ignore


def get_opening_revision(doc):
    all_revisions_ids = Revision.GetAllRevisionIds(doc)
    all_revisions = [doc.GetElement(x) for x in all_revisions_ids]
    rev_strings = [
        "{} - {}".format(rev.RevisionDate, rev.Description) for rev in all_revisions
    ]

    CREATE_NEW_REVISION = "צור מהדורה חדשה"
    rev_strings.append(CREATE_NEW_REVISION)

    selected_rev_str = forms.SelectFromList.show(
        rev_strings, title="בחר מהדורה", multiselect=False
    )
    if not selected_rev_str:
        return

    if selected_rev_str == CREATE_NEW_REVISION:
        t = Transaction(doc, "pyBpm | Create New Revision")
        t.Start()
        rev = Revision.Create(doc)
        rev.RevisionDate = DateTime.Now.ToString("dd/MM/yyyy")
        rev.Description = "עדכון פתחים"
        t.Commit()
        return rev

    selected_rev_index = rev_strings.index(selected_rev_str)
    return all_revisions[selected_rev_index]


def create_revision_clouds(doc, view, bboxes):
    t_group = TransactionGroup(doc, "pyBpm | Create Cloud")
    t_group.Start()

    revision = get_opening_revision(doc)
    if not revision:
        t_group.RollBack()
        return

    level = view.GenLevel
    project_elevation = level.Elevation

    curves_tuples = []
    for bbox in bboxes:
        point1 = XYZ(bbox.Min.X, bbox.Min.Y, project_elevation)
        point2 = XYZ(bbox.Min.X, bbox.Max.Y, project_elevation)
        point3 = XYZ(bbox.Max.X, bbox.Max.Y, project_elevation)
        point4 = XYZ(bbox.Max.X, bbox.Min.Y, project_elevation)

        line1 = Line.CreateBound(point1, point2)
        line2 = Line.CreateBound(point2, point3)
        line3 = Line.CreateBound(point3, point4)
        line4 = Line.CreateBound(point4, point1)

        curve1 = line1
        curve2 = line2
        curve3 = line3
        curve4 = line4

        max_loops = 100
        loop_count = 0
        index_combine = -1
        while True:
            is_intersect = False
            for i, curves_tuple in enumerate(curves_tuples):
                for exist_curve in curves_tuple:
                    for curve in [curve1, curve2, curve3, curve4]:
                        if exist_curve.Intersect(curve) == SetComparisonResult.Overlap:
                            is_intersect = True
                            break
                if is_intersect:
                    exist_point_1 = curves_tuple[0].GetEndPoint(0)
                    exist_point_2 = curves_tuple[1].GetEndPoint(0)
                    exist_point_3 = curves_tuple[2].GetEndPoint(0)
                    exist_point_4 = curves_tuple[3].GetEndPoint(0)
                    old_point1 = point1
                    old_point2 = point2
                    old_point3 = point3
                    old_point4 = point4

                    point1 = XYZ(
                        min(
                            exist_point_1.X,
                            exist_point_2.X,
                            exist_point_3.X,
                            exist_point_4.X,
                            old_point1.X,
                            old_point2.X,
                            old_point3.X,
                            old_point4.X,
                        ),
                        min(
                            exist_point_1.Y,
                            exist_point_2.Y,
                            exist_point_3.Y,
                            exist_point_4.Y,
                            old_point1.Y,
                            old_point2.Y,
                            old_point3.Y,
                            old_point4.Y,
                        ),
                        project_elevation,
                    )
                    point2 = XYZ(
                        min(
                            exist_point_1.X,
                            exist_point_2.X,
                            exist_point_3.X,
                            exist_point_4.X,
                            old_point1.X,
                            old_point2.X,
                            old_point3.X,
                            old_point4.X,
                        ),
                        max(
                            exist_point_1.Y,
                            exist_point_2.Y,
                            exist_point_3.Y,
                            exist_point_4.Y,
                            old_point1.Y,
                            old_point2.Y,
                            old_point3.Y,
                            old_point4.Y,
                        ),
                        project_elevation,
                    )
                    point3 = XYZ(
                        max(
                            exist_point_1.X,
                            exist_point_2.X,
                            exist_point_3.X,
                            exist_point_4.X,
                            old_point1.X,
                            old_point2.X,
                            old_point3.X,
                            old_point4.X,
                        ),
                        max(
                            exist_point_1.Y,
                            exist_point_2.Y,
                            exist_point_3.Y,
                            exist_point_4.Y,
                            old_point1.Y,
                            old_point2.Y,
                            old_point3.Y,
                            old_point4.Y,
                        ),
                        project_elevation,
                    )
                    point4 = XYZ(
                        max(
                            exist_point_1.X,
                            exist_point_2.X,
                            exist_point_3.X,
                            exist_point_4.X,
                            old_point1.X,
                            old_point2.X,
                            old_point3.X,
                            old_point4.X,
                        ),
                        min(
                            exist_point_1.Y,
                            exist_point_2.Y,
                            exist_point_3.Y,
                            exist_point_4.Y,
                            old_point1.Y,
                            old_point2.Y,
                            old_point3.Y,
                            old_point4.Y,
                        ),
                        project_elevation,
                    )

                    line1 = Line.CreateBound(point1, point2)
                    line2 = Line.CreateBound(point2, point3)
                    line3 = Line.CreateBound(point3, point4)
                    line4 = Line.CreateBound(point4, point1)

                    curve1 = line1
                    curve2 = line2
                    curve3 = line3
                    curve4 = line4

                    index_combine = i

                    break
            if not is_intersect:
                break
            loop_count += 1
            if loop_count > max_loops:
                break

        if index_combine != -1:
            curves_tuples[index_combine] = (
                curve1,
                curve2,
                curve3,
                curve4,
            )
        else:
            curves_tuples.append((curve1, curve2, curve3, curve4))

    t = Transaction(doc, "pyBpm | Create Clouds")
    t.Start()

    for curves_tuple in curves_tuples:
        curve1, curve2, curve3, curve4 = curves_tuple
        i_list_curve = List[Curve]([curve1, curve2, curve3, curve4])
        RevisionCloud.Create(doc, view, revision.Id, i_list_curve)

    t.Commit()

    t_group.Assimilate()


def show_opening_3d(uidoc, ui_view, view_3d, bbox):
    doc = uidoc.Document
    turn_of_categories(
        doc,
        view_3d,
        CategoryType.Annotation,
        except_categories=["Section Boxes"],
    )

    opening_filter = get_opening_filter(doc)
    yellow = Color(255, 255, 0)
    ogs = get_ogs_by_color(doc, yellow)
    t1 = Transaction(doc, "pyBpm | Set Opening Filter")
    t1.Start()
    view_3d.SetFilterOverrides(opening_filter.Id, ogs)
    t1.Commit()

    uidoc.ActiveView = view_3d

    t2 = Transaction(doc, "pyBpm | Set Section Boxes")
    t2.Start()
    section_box_increment = 0.4
    bbox_section_box = BoundingBoxXYZ()
    bbox_section_box.Min = bbox.Min.Add(
        XYZ(-section_box_increment, -section_box_increment, -section_box_increment)
    )
    bbox_section_box.Max = bbox.Max.Add(
        XYZ(section_box_increment, section_box_increment, section_box_increment)
    )
    view_3d.SetSectionBox(bbox_section_box)
    t2.Commit()

    zoom_increment = 0.8
    zoom_viewCorner1 = bbox.Min.Add(
        XYZ(-zoom_increment, -zoom_increment, -zoom_increment)
    )
    zoom_viewCorner2 = bbox.Max.Add(XYZ(zoom_increment, zoom_increment, zoom_increment))
    ui_view.ZoomAndCenterRectangle(zoom_viewCorner1, zoom_viewCorner2)


def turn_on_isolate_mode(doc, view):
    t_group = TransactionGroup(doc, "pyBpm | Turn On Isolate Mode")
    t_group.Start()

    t1 = Transaction(doc, "pyBpm | Turn On Isolate Mode")
    t1.Start()
    view.EnableTemporaryViewPropertiesMode(view.Id)
    t1.Commit()

    turn_of_categories(doc, view, CategoryType.Annotation)
    turn_of_categories(doc, view, CategoryType.Model, ["RVT Links", "Generic Models"])

    opening_filter = get_opening_filter(doc)
    yellow = Color(255, 255, 0)
    ogs = get_ogs_by_color(doc, yellow)
    t2 = Transaction(doc, "pyBpm | Set Opening Filter")
    t2.Start()
    view.SetFilterOverrides(opening_filter.Id, ogs)
    t2.Commit()

    not_opening = get_not_opening_filter(doc)
    t3 = Transaction(doc, "pyBpm | Set Not Opening Filter")
    t3.Start()
    view.SetFilterVisibility(not_opening.Id, False)
    t3.Commit()

    t_group.Assimilate()


def turn_off_isolate_mode(doc, view):
    t = Transaction(doc, "pyBpm | Turn Off Isolate Mode")
    t.Start()
    view.EnableTemporaryViewPropertiesMode(ElementId.InvalidElementId)
    t.Commit()


def get_start_end_dates(dates):
    date_dict = {}
    last_last_date = dates[0]
    str_1 = "מהתאריך: {} עד עכשיו.".format(last_last_date.ToString("dd/MM/yyyy"))
    date_dict[str_1] = {
        "start": last_last_date,
        "end": DateTime.Now,
    }
    for i in range(1, len(dates)):
        last_date = dates[i - 1]
        current_date = dates[i]
        str_i = "מהתאריך: {} עד התאריך: {}.".format(
            last_date.ToString("dd/MM/yyyy"), current_date.ToString("dd/MM/yyyy")
        )
        date_dict[str_i] = {
            "start": current_date,
            "end": last_date,
        }

    string_list = list(date_dict.keys())
    selected_date_str = forms.SelectFromList.show(
        string_list, title="בחר תאריכים", multiselect=False
    )
    if not selected_date_str:
        return None, None

    return date_dict[selected_date_str]["start"], date_dict[selected_date_str]["end"]
