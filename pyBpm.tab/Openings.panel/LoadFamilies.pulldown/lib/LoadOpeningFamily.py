# -*- coding: utf-8 -*-
import os

from Autodesk.Revit.DB import FilteredElementCollector, Family, Transaction

from pyrevit import forms
from RevitUtils import (
    get_family_by_name,
)


def get_discipline_from_user():
    """Get the discipline from the user.

    Returns:
        Tuple[str, str]: The discipline code and the discipline name.
    """
    discipline_dict = {
        "A - Architectural": "A",
        "S - Structural": "S",
        "P - Plumbing": "P",
        "SP - Sprinklers": "SP",
        "C - Communications": "C",
        "H - HVAC": "H",
        "E - Electrical": "E",
        "G - Medical Gases": "G",
        "F - Fuel": "F",
    }

    selected_discipline_display = forms.SelectFromList.show(
        discipline_dict.keys(),
        title="Select Discipline",
        multiselect=False,
        button_name="Select",
    )
    if selected_discipline_display is None:
        return None, None
    selected_discipline_code = discipline_dict[selected_discipline_display]
    return selected_discipline_code, selected_discipline_display


def get_family_path(family_name):
    """Returns the full path of the family file."""
    return os.path.join(os.path.dirname(__file__), family_name + ".rfa")


def run(doc, family_names):
    """Load the families into the project.

    Args:
        doc (Autodesk.Revit.DB.Document): _description_
        family_names (str): The names of the families to load.

    Returns:
        List[Autodesk.Revit.DB.Family]: The loaded families.
    """

    messages = []
    messages.append("Load Families Results:")
    messages.append("=" * 14)

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
            t = Transaction(doc, "BPM | Load Opening Families")
            t.Start()
            family_loaded = doc.LoadFamily(get_family_path(family_name))
            t.Commit()
            if family_loaded:
                messages.append("✓ Loaded family: {}".format(family_name))
        else:
            messages.append("⚠ Family already loaded: {}".format(family_name))

    if some_family_already_exist:
        messages.append("")
        messages.append("Note: To reload an existing family, you need to change")
        messages.append("the name of the loaded family or remove it from the project.")

    # Show the collected messages in a single alert
    forms.alert("\n".join(messages), title="Load Families Report")

    families_to_return = []
    for family_name in family_names:
        family = get_family_by_name(doc, family_name)
        if family:
            families_to_return.append(family)
    return families_to_return
