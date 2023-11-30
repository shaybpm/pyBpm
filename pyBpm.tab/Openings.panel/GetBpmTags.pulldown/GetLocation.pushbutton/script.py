# -*- coding: utf-8 -*-
""" Relocation tags by the tags in BPM plan """
__title__ = "Relocation\nTags"
__author__ = "Eyal Sinay"

# -------------------------------
# ------------IMPORTS------------
# -------------------------------

from Autodesk.Revit.DB import (
    Transaction,
)

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
    comp_transform = comp_link.GetTotalTransform()

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

    to_continue = forms.alert(
        "This script will relocate {} Generic Model tags in the active view to the same location as the tags in the Compilation model.\n\nDo you want to continue?".format(
            len(gm_tags_in_view_dict.keys())
        ),
        yes=True,
        cancel=True,
    )
    if not to_continue:
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

        tag_ref = GetBpmTags.get_ref_tag_by_id(tag, gm_id)
        if not tag_ref:
            continue
        comp_ref = GetBpmTags.get_ref_tag_by_id(comp_tag, gm_id)
        if not comp_ref:
            continue

        if GetBpmTags.is_leader_end_supported(
            comp_tag
        ) and GetBpmTags.is_leader_end_supported(tag):
            comp_tag_leader_end = comp_transform.OfPoint(
                comp_tag.GetLeaderEnd(comp_ref)
            )
            tag.SetLeaderEnd(tag_ref, comp_tag_leader_end)

        if RevitUtils.revit_version >= 2022:
            if comp_tag.HasLeaderElbow(comp_ref):
                comp_tag_leader_elbow = comp_transform.OfPoint(
                    comp_tag.GetLeaderElbow(comp_ref)
                )
                tag.SetLeaderElbow(tag_ref, comp_tag_leader_elbow)
        else:
            if comp_tag.HasElbow:
                comp_tag_leader_elbow = comp_transform.OfPoint(comp_tag.LeaderElbow)
                tag.LeaderElbow = comp_tag_leader_elbow
    t.Commit()


run()
