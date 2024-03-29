# -*- coding: utf-8 -*-
import os

from Autodesk.Revit.DB import FilteredElementCollector, Family

from pyrevit import script

# ------------------------------------------------------------
output = script.get_output()
output.close_others()


def get_family_path(family_name):
    """Returns the full path of the family file."""
    return os.path.join(os.path.dirname(__file__), family_name + ".rfa")


def run(doc, family_names):
    output.print_html("<h1>Load Opening Families</h1>")

    some_family_already_exist = False

    for family_name in family_names:
        # Check if the family is already loaded
        family_already_loaded = False
        families = FilteredElementCollector(doc).OfClass(Family)
        for family in families:
            if family.Name == family_name:
                family_already_loaded = True
                some_family_already_exist = True
                break

        # Load the family if it's not loaded
        if not family_already_loaded:
            family_loaded = doc.LoadFamily(get_family_path(family_name))
            if family_loaded:
                output.print_html(
                    '<div style="color:green">Loaded family: ' + family_name + "</div>"
                )
        else:
            output.print_html(
                '<div style="color:yellow; background-color:#020B4A;">Family already loaded: '
                + family_name
                + "</div>"
            )

    if some_family_already_exist:
        output.print_html(
            '<div style="color:blue">If you want to reload family that is already exist, you need to change the name of the family that already loaded, or remove it from the project.</div>'
        )

    families_to_return = []
    for family_name in family_names:
        families = FilteredElementCollector(doc).OfClass(Family)
        for family in families:
            if family.Name == family_name:
                families_to_return.append(family)
    return families_to_return
