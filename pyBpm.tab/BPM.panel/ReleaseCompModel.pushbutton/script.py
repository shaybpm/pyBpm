# -*- coding: utf-8 -*-
""" Forget the compilation model picked for this model.

When the model links more than one compilation model, the first tool that needs
one asks which, and the answer is remembered for this model. This button drops
that answer, so the next tool asks again. """
__title__ = "Release\nComp Model"
__author__ = "Eyal Sinay"

from pyrevit import forms
import RevitUtils

doc = __revit__.ActiveUIDocument.Document  # type: ignore


def run():
    if not doc.IsModelInCloud:
        forms.alert(u"כלי זה זמין רק במודלים בענן (Cloud).")
        return

    saved_key = RevitUtils.get_saved_comp_model_key(doc)
    if not saved_key:
        forms.alert(u"לא נשמרה בחירה של מודל קומפילציה עבור המודל הזה.")
        return

    title = saved_key
    for link in RevitUtils.get_comp_link_candidates(doc):
        if RevitUtils.comp_model_key(link.GetLinkDocument()) == saved_key:
            title = link.GetLinkDocument().Title
            break

    RevitUtils.release_comp_link_choice(doc)
    forms.alert(
        u'הבחירה במודל הקומפילציה "{}" שוחררה.\n'
        u"בפעם הבאה שכלי יזדקק למודל הקומפילציה תתבקש לבחור מחדש.".format(title)
    )


run()
