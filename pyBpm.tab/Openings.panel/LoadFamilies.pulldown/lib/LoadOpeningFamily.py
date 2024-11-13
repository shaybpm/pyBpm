# -*- coding: utf-8 -*-
import os

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    Family,
    Transaction,
    LocationPoint,
)

from pyrevit import script, forms
from RevitUtils import (
    get_family_symbols,
    get_family_symbol_instances,
    getElementName,
    setElementName,
)

# ------------------------------------------------------------
output = script.get_output()
output.close_others()


def get_discipline_from_user():
    """Get the discipline from the user.

    Returns:
        Tuple[str, str]: The discipline code and the discipline name.
    """
    discipline_dict = {
        "A - אדריכלות": "A",
        "S - קונסטרוקציה": "S",
        "P - אינסטלציה": "P",
        "SP - ספרינקלרים": "SP",
        "C - תקשורת": "C",
        "H - מיזוג אוויר": "H",
        "E - חשמל": "E",
        "G - גזים רפואיים": "G",
        "F - דלק": "F",
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


def get_family_by_name(doc, family_name):
    families = FilteredElementCollector(doc).OfClass(Family)
    for family in families:
        if family.Name == family_name:
            return family
    return None


def overwrite_family(family):
    doc = family.Document

    get_failed_html_message = (
        lambda message: '<div style="color:red;">' + message + "</div>"
    )

    html_res = (
        '<div style="color:#06007e; background-color:#ebedef;">Overwrite family: '
        + family.Name
        + "</div>"
    )

    family_symbols = get_family_symbols(family)
    if family_symbols is None:
        return html_res + get_failed_html_message("Failed to get family symbols.")
    if len(family_symbols) != 1:
        return html_res + get_failed_html_message(
            "Family should contain exactly one symbol. Found: "
            + str(len(family_symbols))
        )

    family_symbol = family_symbols[0]
    all_instances = get_family_symbol_instances(family_symbol)

    instances_info_list = []
    for instance in all_instances:
        instances_info = {
            "params": {},
            "reference": instance.HostFace,
            "location": instance.Location.Point,
            "referenceDirection": instance.FacingOrientation,
        }
        for param in instance.Parameters:
            if param.IsReadOnly:
                continue
            if not param.HasValue:
                continue
            storage_type_str = param.StorageType.ToString()
            if storage_type_str == "None":
                continue
            if storage_type_str == "String":
                instances_info["params"][param.Definition.Name] = {
                    "value": param.AsString(),
                    "type": storage_type_str,
                }
            elif storage_type_str == "Double":
                instances_info["params"][param.Definition.Name] = {
                    "value": param.AsDouble(),
                    "type": storage_type_str,
                }
            elif storage_type_str == "Integer":
                instances_info["params"][param.Definition.Name] = {
                    "value": param.AsInteger(),
                    "type": storage_type_str,
                }
            elif storage_type_str == "ElementId":
                instances_info["params"][param.Definition.Name] = {
                    "value": param.AsElementId(),
                    "type": storage_type_str,
                }
            else:
                instances_info["params"][param.Definition.Name] = {
                    "value": param.AsValueString(),
                    "type": storage_type_str,
                }
        instances_info_list.append(instances_info)

    family_name = family.Name

    # Delete the old family
    t1 = Transaction(doc, "BPM | Overwrite Family")
    t1.Start()
    doc.Delete(family.Id)
    t1.Commit()

    # Load the new family
    t2 = Transaction(doc, "BPM | Overwrite Family")
    t2.Start()
    try:
        success_load_new = doc.LoadFamily(get_family_path(family_name))
    except Exception as e:
        t2.RollBack()
        return html_res + get_failed_html_message(str(e))
    t2.Commit()

    if not success_load_new:
        return html_res + get_failed_html_message("Failed to load the new family.")

    # Get the new family
    new_family = get_family_by_name(doc, family_name)
    if new_family is None:
        return html_res + get_failed_html_message("Failed to get the new family.")
    new_family_symbols = get_family_symbols(new_family)
    if new_family_symbols is None:
        return html_res + get_failed_html_message(
            "Failed to get the new family symbols."
        )
    if len(new_family_symbols) != 1:
        return html_res + get_failed_html_message(
            "New family should contain exactly one symbol. Found: "
            + str(len(new_family_symbols))
        )
    new_family_symbol = new_family_symbols[0]
    if not new_family_symbol.IsActive:
        t3 = Transaction(doc, "BPM | Overwrite Family")
        t3.Start()
        new_family_symbol.Activate()
        t3.Commit()

    t4 = Transaction(doc, "BPM | Overwrite Family")
    t4.Start()
    for instances_info in instances_info_list:
        new_instance = doc.Create.NewFamilyInstance(
            instances_info["reference"],
            instances_info["location"],
            instances_info["referenceDirection"],
            new_family_symbol,
        )
        for param_name, param_value in instances_info["params"].items():
            param = new_instance.LookupParameter(param_name)
            if param is None:
                continue
            if param.IsReadOnly:
                continue
            if param.StorageType.ToString() != param_value["type"]:
                continue
            param.Set(param_value["value"])
    t4.Commit()

    return html_res + (
        '<div style="color:green;">Overwrite family succeeded: '
        + family_name
        + "</div>"
    )


def run(doc, family_names, family_already_exist_cb=None):
    """Load the families into the project.

    Args:
        doc (Autodesk.Revit.DB.Document): _description_
        family_names (str): The names of the families to load.
        family_already_exist_cb (Callable): A callback function that will be called if the family already exist. The callback function should accept the family as an argument. It's need to return a html string. Defaults to None.

    Returns:
        List[Autodesk.Revit.DB.Family]: The loaded families.
    """

    output.print_html("<h1>Load Families</h1>")

    some_family_already_exist = False

    for family_name in family_names:
        # Check if the family is already loaded
        family_already_loaded = False
        families = FilteredElementCollector(doc).OfClass(Family)
        target_family = None
        for family in families:
            if family.Name == family_name:
                target_family = family
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
                output.print_html(
                    '<div style="color:green">Loaded family: ' + family_name + "</div>"
                )
        else:
            if family_already_exist_cb is None:
                output.print_html(
                    '<div style="color:yellow; background-color:#020B4A;">Family already loaded: '
                    + family_name
                    + "</div>"
                )
            else:
                html_results = family_already_exist_cb(target_family)
                output.print_html(html_results)

    if some_family_already_exist and family_already_exist_cb is None:
        output.print_html(
            '<div style="color:blue">If you want to reload family that is already exist, you need to change the name of the family that already loaded, or remove it from the project.</div>'
        )

    families_to_return = []
    for family_name in family_names:
        family = get_family_by_name(doc, family_name)
        if family:
            families_to_return.append(family)
    return families_to_return
