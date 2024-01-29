# -*- coding: utf-8 -*-
""" This script replaces the family type of all the tags of the Generic Model category in the view with the type of BPM tags in the Compilation model. """
__title__ = "Replace\nfamily type"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

import clr

clr.AddReferenceByPartialName("System")
from System.Collections.Generic import List

from Autodesk.Revit.DB import Transaction, ElementTransformUtils, ElementId

from pyrevit import forms

import RevitUtils  # type: ignore

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
import GetBpmTags  # type: ignore


# -------------------------------
# -------------MAIN--------------
# -------------------------------

uidoc = __revit__.ActiveUIDocument  # type: ignore
doc = uidoc.Document

# --------------------------------
# -------------SCRIPT-------------
# --------------------------------


def run():
    comp_link = RevitUtils.get_comp_link(doc)
    if not comp_link:
        forms.alert("The Compilation model link is not loaded.")
        return
    comp_doc = comp_link.GetLinkDocument()
    if not comp_doc:
        forms.alert("Something went wrong with the Compilation model link.")
        return

    gm_tags_in_view_dict = GetBpmTags.get_gm_tags_dict(doc, True)
    if not gm_tags_in_view_dict or len(gm_tags_in_view_dict.keys()) == 0:
        forms.alert("No Generic Model tags in the view.")
        return

    gm_tags_in_comp_dict = GetBpmTags.get_gm_tags_dict(comp_doc)
    if not gm_tags_in_comp_dict or len(gm_tags_in_comp_dict.keys()) == 0:
        forms.alert("No Generic Model tags in the Compilation model.")
        return

    gm_tags_in_view_dict = {
        k: v
        for k, v in gm_tags_in_view_dict.items()
        if k in gm_tags_in_comp_dict.keys()
    }

    t = Transaction(doc, "BPM | Replace Tag family types")
    t.Start()
    counter = 0
    for gm_id in gm_tags_in_view_dict.keys():
        tag = gm_tags_in_view_dict[gm_id]
        comp_tag = gm_tags_in_comp_dict.get(gm_id)
        if not comp_tag:
            continue
        comp_tag_type = comp_doc.GetElement(comp_tag.GetTypeId())
        comp_tag_type_name = RevitUtils.getElementName(comp_tag_type)
        comp_tag_type_family_name = comp_tag_type.Family.Name

        tag_type = doc.GetElement(tag.GetTypeId())
        tag_type_name = RevitUtils.getElementName(tag_type)
        tag_type_family_name = tag_type.Family.Name
        if (
            tag_type_name == comp_tag_type_name
            and tag_type_family_name == comp_tag_type_family_name
        ):
            continue

        comp_tag_type_in_doc = GetBpmTags.get_type(
            doc, comp_tag_type_family_name, comp_tag_type_name
        )
        if not comp_tag_type_in_doc:
            copies_ids = ElementTransformUtils.CopyElements(
                comp_doc, List[ElementId]([comp_tag.GetTypeId()]), doc, None, None
            )
            if not copies_ids or len(copies_ids) == 0:
                continue
            comp_tag_type_in_doc = doc.GetElement(copies_ids[0])
        tag.ChangeTypeId(comp_tag_type_in_doc.Id)
        counter += 1

    if counter > 0:
        to_commit = forms.alert(
            "This script will replace the family types of {} Generic Model tags in the active view.\n\nDo you want to continue?".format(
                counter
            ),
            yes=True,
            cancel=True,
        )
        if not to_commit:
            t.RollBack()
            return
    else:
        t.RollBack()
        forms.alert("No Family types to replace.")
        return

    t.Commit()


run()
