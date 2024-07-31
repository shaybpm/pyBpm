# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (
    TransactionGroup,
    Transaction,
    Color,
    ElementId,
    CategoryType,
)
from RevitUtils import (
    turn_of_categories,
    get_ogs_by_color,
)
from RevitUtilsOpenings import get_opening_filter, get_not_opening_filter
from ExEventHandlers import get_simple_external_event


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
