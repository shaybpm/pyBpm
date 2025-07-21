# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (
    TransactionGroup,
    ViewType,
    FilteredElementCollector,
    View,
    Transaction,
    Color,
    OverrideGraphicSettings,
)
import Utils
from RevitUtils import (
    get_ui_view,
    get_bpm_3d_view,
    get_tags_of_element_in_view,
    get_ogs_by_color,
)
from RevitUtilsOpenings import (
    create_or_modify_specific_openings_filter,
    add_one_opening_to_specific_openings_filter,
    remove_one_opening_from_specific_openings_filter,
)
from ExEventHandlers import get_simple_external_event

from ExternalEventDataFile import ExternalEventDataFile


def show_opening_3d_cb(uiapp):
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document

    ex_event_file = ExternalEventDataFile(doc)
    opening = ex_event_file.get_key_value("current_selected_opening")
    current = ex_event_file.get_key_value("current_bool_arg")

    t_group = TransactionGroup(doc, "pyBpm | Show Opening 3D")
    t_group.Start()

    if not opening:
        t_group.RollBack()
        return

    if current is None:
        t_group.RollBack()
        return

    bbox = Utils.get_bbox(doc, opening, current)
    if not bbox:
        t_group.RollBack()
        return

    ui_view = get_ui_view(uidoc)
    if not ui_view:
        t_group.RollBack()
        return

    view_3d = get_bpm_3d_view(doc)
    if not view_3d:
        Utils.alert("תקלה בקבלת תצוגת 3D")
        t_group.RollBack()
        return
    Utils.show_opening_3d(uidoc, ui_view, view_3d, bbox)
    t_group.Assimilate()


show_opening_3d_event = get_simple_external_event(show_opening_3d_cb)


def create_revision_clouds_cb(uiapp):
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document

    ex_event_file = ExternalEventDataFile(doc)

    active_view = uidoc.ActiveView
    if active_view.ViewType not in [
        ViewType.FloorPlan,
        ViewType.CeilingPlan,
        ViewType.EngineeringPlan,
    ]:
        Utils.alert("לא זמין במבט זה")
        return

    current_selected_opening = ex_event_file.get_key_value("current_selected_opening")
    if not current_selected_opening:
        Utils.alert("יש לבחור פתחים")
        return

    t_group = TransactionGroup(doc, "pyBpm | Create Revision Clouds")
    t_group.Start()
    bboxes = []
    for opening in current_selected_opening:
        opening_tags = get_tags_of_element_in_view(active_view, opening["uniqueId"])
        if len(opening_tags) == 0:
            bbox = Utils.get_bbox(doc, opening, current=not opening["isDeleted"])
            if bbox:
                bboxes.append(bbox)
        else:
            for tag in opening_tags:
                bbox = Utils.get_head_tag_bbox(tag, active_view)
                if bbox:
                    bboxes.append(bbox)

    if len(bboxes) == 0:
        t_group.RollBack()
        return

    Utils.create_revision_clouds(doc, active_view, bboxes)
    t_group.Assimilate()


create_revision_clouds_event = get_simple_external_event(create_revision_clouds_cb)


def filters_in_views_cb(uiapp):
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document

    ex_event_file = ExternalEventDataFile(doc)

    filters_in_views_settings = ex_event_file.get_key_value("filters_in_views_settings")
    if not filters_in_views_settings:
        Utils.alert("not filters_in_views_settings")
        return

    openings = filters_in_views_settings["openings"]
    if not openings:
        Utils.alert("not openings")
        return

    views_app = filters_in_views_settings["views"]
    if not views_app:
        Utils.alert("not views_app")
        return

    views = FilteredElementCollector(doc).OfClass(View).ToElements()

    def get_view_by_id_int(id_int):
        for view in views:
            if view.Id.IntegerValue == id_int:
                return view
        return None

    t_group = TransactionGroup(doc, "pyBpm | Filters In Views")
    t_group.Start()

    specific_openings_filter = create_or_modify_specific_openings_filter(doc, openings)
    if not specific_openings_filter:
        t_group.RollBack()
        Utils.alert("not specific_openings_filter")
        return

    t2 = Transaction(doc, "pyBpm | Filters In Views")
    t2.Start()
    for view_app in views_app:
        view_id = view_app["view_id"]
        view = get_view_by_id_int(view_id)
        if not view:
            continue
        apply = view_app["apply"]
        if apply == False and not view.IsFilterApplied(specific_openings_filter.Id):
            continue
        if filters_in_views_settings["hide_openings"]:
            view.SetFilterVisibility(specific_openings_filter.Id, not apply)
        elif filters_in_views_settings["color_openings"]:
            view.SetFilterVisibility(specific_openings_filter.Id, True)
            if apply:
                ogs = get_ogs_by_color(
                    doc,
                    Color(
                        filters_in_views_settings["color"]["red"],
                        filters_in_views_settings["color"]["green"],
                        filters_in_views_settings["color"]["blue"],
                    ),
                )
                view.SetFilterOverrides(specific_openings_filter.Id, ogs)
            else:
                view.SetFilterOverrides(
                    specific_openings_filter.Id, OverrideGraphicSettings()
                )
        else:
            raise Exception("Unknown operation")
    t2.Commit()

    t_group.Assimilate()


filters_in_views_event = get_simple_external_event(filters_in_views_cb)


def change_specific_openings_filter_cb(uiapp):
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document

    ex_event_file = ExternalEventDataFile(doc)

    openings_with_new_approved_status = ex_event_file.get_key_value(
        "change_specific_openings_filter_data"
    )
    if not openings_with_new_approved_status:
        Utils.alert("not openings_with_new_approved_status")
        return

    openings_by_new_approved_status = {}
    for opening in openings_with_new_approved_status:
        new_approved_status = opening["new_approved_status"]
        if new_approved_status not in openings_by_new_approved_status:
            openings_by_new_approved_status[new_approved_status] = []
        openings_by_new_approved_status[new_approved_status].append(opening)

    try:
        t_group = TransactionGroup(doc, "pyBpm | Change Filter")
        t_group.Start()
        for new_approved_status, openings in openings_by_new_approved_status.items():
            change_func = (
                add_one_opening_to_specific_openings_filter
                if new_approved_status == "not approved"
                else remove_one_opening_from_specific_openings_filter
            )
            for opening in openings:
                change_func(doc, opening)
        t_group.Assimilate()
    except Exception as ex:
        print(ex)
        t_group.RollBack()


change_specific_openings_filter_event = get_simple_external_event(
    change_specific_openings_filter_cb
)
