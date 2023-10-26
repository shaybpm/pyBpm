# -*- coding: utf-8 -*-
""" Relocation tags by the tags in BPM plan """
__title__ = "Get BPM\nTag Location"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    IndependentTag,
    RevitLinkInstance,
    Transaction,
)

# from Autodesk.Revit.UI import ...

from pyrevit import forms

import RevitUtils  # type: ignore

# import HttpRequest  # type: ignore
# import PyUtils  # type: ignore

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document
# selection = [doc.GetElement(x) for x in uidoc.Selection.GetElementIds()]

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------

# opening_unique_id = "07559ab8-d2df-471b-bf87-41f6cbf1c8f8-00273c21"


def get_linked_element(id):
    all_links = FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()
    for link in all_links:
        doc_link = link.GetLinkDocument()
        if doc_link:
            element = doc_link.GetElement(id)
            if element:
                return element


def get_gm_tags_dict(_doc, in_active_view=False):
    all_tags_in_view = (
        (
            FilteredElementCollector(_doc, doc.ActiveView.Id)
            .OfClass(IndependentTag)
            .ToElements()
        )
        if in_active_view
        else (FilteredElementCollector(_doc).OfClass(IndependentTag).ToElements())
    )
    gm_tags = {}
    for tag in all_tags_in_view:
        refs = None
        if RevitUtils.revit_version < 2022:
            refs = [tag.GetTaggedReference()]
        else:
            refs = tag.GetTaggedReferences()
        if not refs or len(refs) == 0:
            continue
        for ref in refs:
            linked_element_id = ref.LinkedElementId
            if not linked_element_id:
                continue
            tagged_element = get_linked_element(linked_element_id)
            if not tagged_element:
                continue
            if not tagged_element.Category:
                continue
            if tagged_element.Category.Name == "Generic Models":
                gm_tags[tagged_element.UniqueId] = tag
    return gm_tags


def run():
    comp_link = RevitUtils.get_comp_link(doc)
    if not comp_link:
        forms.alert("The Compilation model link is not loaded.")
        return
    comp_doc = comp_link.GetLinkDocument()
    if not comp_doc:
        forms.alert("Something went wrong with the Compilation model link.")
        return
    comp_transform = comp_link.GetTotalTransform()

    gm_tags_in_view_dict = get_gm_tags_dict(doc, True)
    if not gm_tags_in_view_dict or len(gm_tags_in_view_dict.keys()) == 0:
        forms.alert("No Generic Model tags in the view.")
        return

    gm_tags_in_comp_dict = get_gm_tags_dict(comp_doc)
    if not gm_tags_in_comp_dict or len(gm_tags_in_comp_dict.keys()) == 0:
        forms.alert("No Generic Model tags in the Compilation model.")
        return

    t = Transaction(doc, "BPM | Relocate Tags")
    t.Start()
    for gm_id in gm_tags_in_view_dict.keys():
        tag = gm_tags_in_view_dict[gm_id]
        comp_tag = gm_tags_in_comp_dict.get(gm_id)
        if not comp_tag:
            continue
        tag.HasLeader = comp_tag.HasLeader
        if tag.CanLeaderEndConditionBeAssigned(comp_tag.LeaderEndCondition):
            tag.LeaderEndCondition = comp_tag.LeaderEndCondition
        tag.TagOrientation = comp_tag.TagOrientation
        tag.TagHeadPosition = comp_transform.OfPoint(comp_tag.TagHeadPosition)

        # comp_tag_leader_end = comp_transform.OfPoint(comp_tag.GetLeaderEnd())
        # tag.SetLeaderEnd(comp_tag_leader_end)
        # if comp_tag.HasLeaderElbow():
        #     comp_tag_leader_elbow = comp_transform.OfPoint(comp_tag.GetLeaderElbow())
        #     tag.SetLeaderElbow(comp_tag_leader_elbow)
    t.Commit()


run()
