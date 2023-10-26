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


def get_all_gm_tags_in_view():
    all_tags_in_view = (
        FilteredElementCollector(doc, doc.ActiveView.Id)
        .OfClass(IndependentTag)
        .ToElements()
    )
    gm_tags = []
    for tag in all_tags_in_view:
        ref = None
        if RevitUtils.revit_version < 2022:
            ref = tag.GetTaggedReference()
        else:
            refs = tag.GetTaggedReferences()
            if refs and len(refs) > 0:
                ref = refs[0]
        if not ref:
            continue
        linked_element_id = ref.LinkedElementId
        if not linked_element_id:
            continue
        tagged_element = get_linked_element(linked_element_id)
        if not tagged_element:
            continue
        if not tagged_element.Category:
            continue
        if tagged_element.Category.Name == "Generic Models":
            gm_tags.append(tag)
    return gm_tags


def run():
    comp_link = RevitUtils.get_comp_link(doc)
    if not comp_link:
        forms.alert("The Compilation model link is not loaded.")
        return

    all_gm_tags_in_view = get_all_gm_tags_in_view()
    print(all_gm_tags_in_view)


run()
