# -*- coding: utf-8 -*-

from pyrevit import forms

from OverwriteFamilyDialog import OverwriteFamilyDialog

from RevitUtils import get_family_by_name


def run(doc, family_names):
    selected_family_name = forms.SelectFromList.show(
        family_names,
        title="Select One Family",
        multiselect=False,
        button_name="Select",
    )
    if selected_family_name is None:
        return

    family = get_family_by_name(doc, selected_family_name)
    if not family:
        forms.alert(
            "This family does not exist in the project.\nYou can load it by clicking this button without holding the Shift key.",
            title="Family Not Found",
        )
        return

    overwrite_family_dialog = OverwriteFamilyDialog(family)
    overwrite_family_dialog.Show()
