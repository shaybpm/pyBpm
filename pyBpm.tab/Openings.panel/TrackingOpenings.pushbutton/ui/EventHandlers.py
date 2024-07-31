# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (
    TransactionGroup,
    Transaction,
    ViewType,
    Color,
    ElementId,
    CategoryType,
)
import Utils
from RevitUtils import (
    get_ui_view,
    get_bpm_3d_view,
    get_tags_of_element_in_view,
    turn_of_categories,
    get_ogs_by_color,
)
from RevitUtilsOpenings import get_opening_filter, get_not_opening_filter
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


def turn_on_isolate_mode_db(uiapp):
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


turn_on_isolate_mode_event = get_simple_external_event(turn_on_isolate_mode_db)


def turn_off_isolate_mode_db(uiapp):
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document
    view = uidoc.ActiveView

    t = Transaction(doc, "pyBpm | Turn Off Isolate Mode")
    t.Start()
    view.EnableTemporaryViewPropertiesMode(ElementId.InvalidElementId)
    t.Commit()


turn_off_isolate_mode_event = get_simple_external_event(turn_off_isolate_mode_db)
