# -*- coding: utf-8 -*-

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    IndependentTag,
    RevitLinkInstance,
    LeaderEndCondition,
    Family,
)

import RevitUtils

# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document
# selection = [doc.GetElement(x) for x in uidoc.Selection.GetElementIds()]

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


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
        if RevitUtils.getRevitVersion(doc) < 2022:
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


def get_ref_tag_by_id(tag, id):
    refs = None
    if RevitUtils.getRevitVersion(doc) < 2022:
        refs = [tag.GetTaggedReference()]
    else:
        refs = tag.GetTaggedReferences()
    if not refs or len(refs) == 0:
        return None
    for ref in refs:
        linked_element_id = ref.LinkedElementId
        if not linked_element_id:
            continue
        tagged_element = get_linked_element(linked_element_id)
        if not tagged_element:
            continue
        if tagged_element.UniqueId == id:
            return ref


def is_leader_end_supported(tag):
    """Tags with attached leaders or no leaders do not support leader ends"""
    if not tag.HasLeader:
        return False
    if tag.LeaderEndCondition == LeaderEndCondition.Attached:
        return False
    return True


def get_type(doc, family_name, type_name):
    all_families = FilteredElementCollector(doc).OfClass(Family).ToElements()
    for family in all_families:
        if family.Name != family_name:
            continue
        type_ids = family.GetFamilySymbolIds()
        if not type_ids or len(type_ids) == 0:
            continue
        types = [doc.GetElement(x) for x in type_ids]
        for type in types:
            if RevitUtils.getElementName(type) == type_name:
                return type
    return None
