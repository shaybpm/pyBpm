import os, sys
from Autodesk.Revit.DB import ElementId, Transaction, TransactionGroup
from RevitUtils import (
    getElementName,
    setElementName,
    get_family_by_name,
    get_family_symbols,
    activate_family_symbol,
)
from ExEventHandlers import get_simple_external_event
from ExternalEventDataFile import ExternalEventDataFile
from Config import root_path

parameter_names_to_restore = [
    "Mark",
    "D",
    "b",
    "h",
    "Depth",
    "Depth Offset",
    "Additional Bottom Cut Offset",
    "Additional Top Cut Offset",
    "Cut Offset",
    "Face Offset",
    "Detail - Yes / No",
]


def get_family_path(family_name):
    """Returns the full path of the family file."""
    return os.path.join(os.path.dirname(__file__), family_name + ".rfa")


def rename_current_family(uiapp):
    try:
        uidoc = uiapp.ActiveUIDocument
        doc = uidoc.Document

        ex_event_file = ExternalEventDataFile(
            doc, instead_bundle_name="OVERWRITE_FAMILY"
        )
        current_family_id = ex_event_file.get_key_value("current_family_id")
        family = doc.GetElement(ElementId(int(current_family_id)))

        current_family_symbol_id = ex_event_file.get_key_value(
            "current_family_symbol_id"
        )
        family_symbol = doc.GetElement(ElementId(int(current_family_symbol_id)))

        # Change family name and symbol name
        family_name = family.Name
        temp_family_name = family_name + "_temp"
        symbol_name = getElementName(family_symbol)
        temp_symbol_name = symbol_name + "_temp"
        t = Transaction(doc, "BPM | Rename Family")
        t.Start()
        family.Name = temp_family_name
        setElementName(family_symbol, temp_symbol_name)
        t.Commit()
    except Exception as e:
        print(e)


rename_current_family_event = get_simple_external_event(rename_current_family)


def load_new_family(uiapp):
    try:
        uidoc = uiapp.ActiveUIDocument
        doc = uidoc.Document

        ex_event_file = ExternalEventDataFile(
            doc, instead_bundle_name="OVERWRITE_FAMILY"
        )

        family_name = ex_event_file.get_key_value("current_family_name")
        family_path = get_family_path(family_name)

        t_group = TransactionGroup(doc, "BPM | Load New Family")
        t_group.Start()

        t1 = Transaction(doc, "BPM | Load New Family")
        t1.Start()
        success_load_new = doc.LoadFamily(family_path)
        if not success_load_new:
            t1.RollBack()
            return
        t1.Commit()

        # Get the new family
        new_family = get_family_by_name(doc, family_name)
        if new_family is None:
            return
        new_family_symbols = get_family_symbols(new_family)
        if new_family_symbols is None:
            return
        if len(new_family_symbols) != 1:
            return
        new_family_symbol = new_family_symbols[0]

        # Activate the new family symbol
        # t2 is inside the activate_family_symbol function
        activate_family_symbol(new_family_symbol)

        # set the description parameter of the new family symbol
        new_family_symbol_description = ex_event_file.get_key_value(
            "current_family_symbol_description"
        )
        if new_family_symbol_description:
            t3 = Transaction(doc, "BPM | Set Family Symbol Description")
            t3.Start()
            new_family_symbol.LookupParameter("Description").Set(
                new_family_symbol_description
            )
            t3.Commit()

        t_group.Assimilate()

        # add the id of the new family and the new family symbol to the external event data file
        ex_event_file.set_key_value("new_family_id", new_family.Id.ToString())
        ex_event_file.set_key_value(
            "new_family_symbol_id", new_family_symbol.Id.ToString()
        )
    except Exception as e:
        print(e)


load_new_family_event = get_simple_external_event(load_new_family)


def change_family_symbol(uiapp):
    try:
        uidoc = uiapp.ActiveUIDocument
        doc = uidoc.Document

        ex_event_file = ExternalEventDataFile(
            doc, instead_bundle_name="OVERWRITE_FAMILY"
        )

        new_family_symbol_id = ex_event_file.get_key_value("new_family_symbol_id")
        new_family_symbol = doc.GetElement(ElementId(int(new_family_symbol_id)))

        instances_param_dict = ex_event_file.get_key_value("instances_param_dict")

        # For each instance, change the symbol to the new symbol.
        t = Transaction(doc, "BPM | Change Family Symbol")
        t.Start()
        for instance_id_str in instances_param_dict:
            instance = doc.GetElement(ElementId(int(instance_id_str)))
            if instance is None:
                raise Exception("Failed to get instance by id: " + instance_id_str)
            instance.Symbol = new_family_symbol
        t.Commit()
    except Exception as e:
        print(e)


change_family_symbol_event = get_simple_external_event(change_family_symbol)


def restore_parameters(uiapp):
    try:
        uidoc = uiapp.ActiveUIDocument
        doc = uidoc.Document

        ex_event_file = ExternalEventDataFile(
            doc, instead_bundle_name="OVERWRITE_FAMILY"
        )

        instances_param_dict = ex_event_file.get_key_value("instances_param_dict")

        # For each instance, set the parameters
        t4 = Transaction(doc, "BPM | Restore Parameters")
        t4.Start()
        for instance_id_str, param_dict in instances_param_dict.items():
            instance = doc.GetElement(ElementId(int(instance_id_str)))
            if instance is None:
                raise Exception("Failed to get instance by id: " + instance_id_str)
            for param_name, param_vt_dict in param_dict.items():
                param = instance.LookupParameter(param_name)
                if param is None:
                    continue
                if param.IsReadOnly:
                    continue
                if param.StorageType.ToString() != param_vt_dict["type"]:
                    continue
                if param_name not in parameter_names_to_restore:
                    continue
                value = (
                    param_vt_dict["value"]
                    if param_vt_dict["type"] != "ElementId"
                    else ElementId(int(param_vt_dict["value"]))
                )
                param.Set(value)
        t4.Commit()
    except Exception as e:
        print(e)


restore_parameters_event = get_simple_external_event(restore_parameters)


def delete_old_family(uiapp):
    try:
        uidoc = uiapp.ActiveUIDocument
        doc = uidoc.Document

        ex_event_file = ExternalEventDataFile(
            doc, instead_bundle_name="OVERWRITE_FAMILY"
        )

        current_family_id = ex_event_file.get_key_value("current_family_id")
        old_family_id = ElementId(int(current_family_id))

        t = Transaction(doc, "BPM | Delete Old Family")
        t.Start()
        doc.Delete(old_family_id)
        t.Commit()
    except Exception as e:
        print(e)


delete_old_family_event = get_simple_external_event(delete_old_family)


def run_opening_set(uiapp):
    # NOTE:
    # For some reason, this causes when the user closes Revit they get a note saying that Revit was closed incorrectly.
    # For now, we'll just ask the user to run "Opening Set" themselves.

    sys.path.append(
        os.path.join(
            root_path, "pyBpm.tab", "Openings.panel", "OpeningSet.pushbutton", "lib"
        )
    )
    import OpeningSet  # type: ignore
    import PrintResults  # type: ignore
    from RevitUtilsOpenings import get_all_openings

    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document

    from pyrevit import script

    output = script.get_output()

    all_openings = get_all_openings(doc)

    t = Transaction(doc, "BPM | Opening Set")
    t.Start()

    failOpt = t.GetFailureHandlingOptions()
    preprocessor = OpeningSet.Preprocessor()
    failOpt.SetFailuresPreprocessor(preprocessor)
    t.SetFailureHandlingOptions(failOpt)

    results = OpeningSet.execute_all_functions_for_all_openings(doc, all_openings, True)

    PrintResults.print_results(output, results)

    t.Commit()


run_opening_set_event = get_simple_external_event(run_opening_set)
