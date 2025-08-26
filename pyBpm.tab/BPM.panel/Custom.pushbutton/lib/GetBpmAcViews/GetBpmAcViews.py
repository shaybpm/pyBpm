# -*- coding: utf-8 -*-
import clr

clr.AddReferenceByPartialName("System")
from System.Collections.Generic import List
from pyrevit.forms import alert
from RevitUtils import get_comp_link
from Autodesk.Revit.DB import (
    Transaction,
    FilteredElementCollector,
    View,
    ElementId,
    ElementTransformUtils,
)


def get_ac_view_templates(doc):
    views = FilteredElementCollector(doc).OfClass(View).ToElements()
    return [v for v in views if v.IsTemplate and v.Name.startswith("01_AC")]


def get_bpm_ac_view_template_ids(comp_doc, doc):
    doc_view_templates = get_ac_view_templates(doc)
    doc_view_template_names = {v.Name for v in doc_view_templates}

    comp_doc_view_templates = get_ac_view_templates(comp_doc)
    ac_view_template_ids = List[ElementId]()
    for comp_v_t in comp_doc_view_templates:
        if comp_v_t.Name not in doc_view_template_names:
            ac_view_template_ids.Add(comp_v_t.Id)

    return ac_view_template_ids


def get_bpm_ac_view_templates(uidoc):
    doc = uidoc.Document
    comp_link = get_comp_link(doc)
    if not comp_link:
        alert("The Compilation model link is not loaded.")
        return

    comp_doc = comp_link.GetLinkDocument()
    if not comp_doc:
        alert(
            "Something went wrong with the Compilation model link.\nmaybe it's not loaded?"
        )
        return

    bpm_ac_view_template_ids = get_bpm_ac_view_template_ids(comp_doc, doc)
    if bpm_ac_view_template_ids.Count == 0:
        alert("No new view templates to copy.")
        return

    t = Transaction(doc, "BPM | Get BPM AC View Templates")
    t.Start()
    try:
        ElementTransformUtils.CopyElements(
            comp_doc, bpm_ac_view_template_ids, doc, None, None
        )
        t.Commit()
    except Exception as e:
        t.RollBack()
        alert("Failed to copy view templates.\n{}".format(e))
        return
