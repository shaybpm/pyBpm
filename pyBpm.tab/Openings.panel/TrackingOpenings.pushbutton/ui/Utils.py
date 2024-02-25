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
)

from System.Collections.Generic import List

from pyrevit import forms

from RevitUtils import turn_of_categories, get_ogs_by_color, get_transform_by_model_guid

from RevitUtilsOpenings import get_opening_filter

from CreateCloudsDialog import CreateCloudsDialog


def get_bbox(doc, opening, current=True, prompt_alert=True):
    transform = get_transform_by_model_guid(doc, opening["modelGuid"])
    if not transform:
        forms.alert("לא נמצא הלינק של הפתח הנבחר")
        return

    bbox_key_name = "currentBBox" if current else "lastBBox"
    if bbox_key_name not in opening or opening[bbox_key_name] is None:
        if prompt_alert:
            msg = "לא נמצא מיקום הפתח הנבחר.\n{}".format(
                'מפני שזהו אלמנט חדש, עליך ללחוץ על "הצג פתח".'
                if not current
                else 'מפני שזהו אלמנט שנמחק, עליך ללחוץ על "הצג מיקום קודם".'
            )
            forms.alert(msg)
        return
    db_bbox = opening[bbox_key_name]

    bbox = BoundingBoxXYZ()
    point_1 = transform.OfPoint(
        XYZ(db_bbox["min"]["x"], db_bbox["min"]["y"], db_bbox["min"]["z"])
    )
    point_2 = transform.OfPoint(
        XYZ(db_bbox["max"]["x"], db_bbox["max"]["y"], db_bbox["max"]["z"])
    )

    min_x = min(point_1.X, point_2.X)
    min_y = min(point_1.Y, point_2.Y)
    min_z = min(point_1.Z, point_2.Z)
    max_x = max(point_1.X, point_2.X)
    max_y = max(point_1.Y, point_2.Y)
    max_z = max(point_1.Z, point_2.Z)

    bbox.Min = XYZ(min_x, min_y, min_z)
    bbox.Max = XYZ(max_x, max_y, max_z)

    return bbox


def get_opening_revision_and_size(doc):
    """
    Get the revision and the cloud size from the user.

    Cloud sizes: ["small", "medium", "large"]
    """
    create_clouds_dialog = CreateCloudsDialog(doc)
    user_values = create_clouds_dialog.show_dialog()
    if not user_values:
        return

    if user_values["create_revision"]:
        t = Transaction(doc, "pyBpm | Create New Revision")
        t.Start()
        rev = Revision.Create(doc)
        rev.RevisionDate = DateTime.Now.ToString("dd/MM/yyyy")
        rev.Description = "עדכון פתחים"
        t.Commit()
        return rev, user_values["cloud_size"]

    return user_values["revision"], user_values["cloud_size"]


def create_revision_clouds(doc, view, bboxes):
    t_group = TransactionGroup(doc, "pyBpm | Create Cloud")
    t_group.Start()

    revision, cloud_size = get_opening_revision_and_size(doc)
    if not revision:
        t_group.RollBack()
        return
    if not cloud_size or cloud_size not in ["small", "medium", "large"]:
        print("ERROR: Cloud size not valid.")
        t_group.RollBack()
        return

    level = view.GenLevel
    project_elevation = level.Elevation

    increase_value_dict = {
        "small": 0.0,
        "medium": 0.3,
        "large": 0.6,
    }
    increase_value = increase_value_dict[cloud_size]

    curves_tuples = []
    for bbox in bboxes:
        point1 = XYZ(
            bbox.Min.X - increase_value, bbox.Min.Y - increase_value, project_elevation
        )
        point2 = XYZ(
            bbox.Min.X - increase_value, bbox.Max.Y + increase_value, project_elevation
        )
        point3 = XYZ(
            bbox.Max.X + increase_value, bbox.Max.Y + increase_value, project_elevation
        )
        point4 = XYZ(
            bbox.Max.X + increase_value, bbox.Min.Y - increase_value, project_elevation
        )

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

        # TODO: check: Application.ShortCurveTolerance
        try:
            RevisionCloud.Create(doc, view, revision.Id, i_list_curve)
        except Exception as ex:
            print("ERROR:")
            print("Cloud Revision not created.")
            print(ex)

        # TODO: Add opening names to comments

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


def filter_sheets(view_sheet):
    folder_param = view_sheet.LookupParameter("Folder")
    if not folder_param:
        return False
    folder = folder_param.AsString()
    if not folder:
        return False
    if not folder.startswith("04_"):
        return False
    return True


def get_start_end_dates(dates):
    date_dict = {}
    last_last_date = dates[0]
    str_1 = "מהתאריך: {} עד עכשיו.".format(last_last_date.ToString("dd.MM.yyyy"))
    date_dict[str_1] = {
        "start": last_last_date,
        "end": DateTime.Now,
    }
    for i in range(1, len(dates)):
        last_date = dates[i - 1]
        current_date = dates[i]
        str_i = "מהתאריך: {} עד התאריך: {}.".format(
            last_date.ToString("dd.MM.yyyy"), current_date.ToString("dd.MM.yyyy")
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


def get_new_opening_approved_status(openings, new_approved_status):
    new_status_list = []
    for opening in openings:
        new_status_list.append(
            {
                "uniqueId": opening["uniqueId"],
                "approved": new_approved_status,
            }
        )
    return new_status_list


def get_head_tag_bbox(tag, view):
    tag_has_leader = tag.HasLeader

    def change_tag_has_leader(has):
        doc = tag.Document
        t1 = Transaction(doc, "pyBpm | change_tag_has_leader")
        t1.Start()
        tag.HasLeader = has
        t1.Commit()

    t_group = TransactionGroup(tag.Document, "pyBpm | Get Tag BBox")
    t_group.Start()

    if tag_has_leader:
        change_tag_has_leader(False)

    tag_bbox = tag.get_BoundingBox(view)
    if not tag_bbox:
        if tag_has_leader:
            change_tag_has_leader(True)
        return None

    if tag_has_leader:
        change_tag_has_leader(True)

    t_group.Assimilate()
    return tag_bbox
