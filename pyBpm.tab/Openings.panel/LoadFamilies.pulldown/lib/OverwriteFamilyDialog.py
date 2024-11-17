# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
import wpf
import os

from RevitUtils import get_family_symbols, get_family_symbol_instances
from ExternalEventDataFile import ExternalEventDataFile

from OverwriteFamilyEventHandlers import (
    parameter_names_to_restore,
    rename_current_family_event,
    load_new_family_event,
    change_family_symbol_event,
    restore_parameters_event,
    delete_old_family_event,
    # run_opening_set_event,
)

xaml_file = os.path.join(os.path.dirname(__file__), "OverwriteFamilyDialogUi.xaml")


class OverwriteFamilyDialog(Windows.Window):
    def __init__(self, family):
        wpf.LoadComponent(self, xaml_file)
        self.family = family
        self._step = 0

        self.Title = "Overwrite Family: {}".format(family.Name)

        self.messages = [
            "Rename the current family and symbol, so we can late load the new family.",
            "Load the new family.",
            "Change the family symbol for all instances.",
            "Restore the parameters.",
            "Delete the old family.",
            'Finished!\nPlease close this dialog and run the "Opening Set" command.',
        ]
        self.button_contents = [
            "Rename Current Family",
            "Load New Family",
            "Change Family Symbol",
            "Restore Parameters",
            "Delete Old Family",
            "Close",
        ]

        self.doc = family.Document
        self.ex_event_file = ExternalEventDataFile(
            self.doc, instead_bundle_name="OVERWRITE_FAMILY"
        )
        self.ex_event_file.set_key_value("current_family_id", family.Id.ToString())
        self.ex_event_file.set_key_value("current_family_name", family.Name)

        family_symbols = get_family_symbols(family)
        if family_symbols is None:
            raise Exception("Failed to get family symbols.")
        if len(family_symbols) != 1:
            raise Exception(
                "Family should contain exactly one symbol. Found: "
                + str(len(family_symbols))
            )

        family_symbol = family_symbols[0]
        self.ex_event_file.set_key_value(
            "current_family_symbol_id", family_symbol.Id.ToString()
        )

        family_symbol_description_param = family_symbol.LookupParameter("Description")
        family_symbol_description_value = ""
        if family_symbol_description_param is not None:
            family_symbol_description_value = (
                family_symbol_description_param.AsString() or ""
            )
        self.ex_event_file.set_key_value(
            "current_family_symbol_description", family_symbol_description_value
        )

        all_instances = get_family_symbol_instances(family_symbol)

        self.instances_param_dict = {}
        for instance in all_instances:
            instance_id_str = instance.Id.ToString()
            if instance_id_str not in self.instances_param_dict:
                self.instances_param_dict[instance_id_str] = {}
            for param in instance.Parameters:
                param_name = param.Definition.Name
                if param_name not in parameter_names_to_restore:
                    continue
                if param.IsReadOnly:
                    continue
                if not param.HasValue:
                    continue
                storage_type_str = param.StorageType.ToString()
                if storage_type_str == "None":
                    continue
                if storage_type_str == "String":
                    self.instances_param_dict[instance_id_str][param_name] = {
                        "value": param.AsString(),
                        "type": storage_type_str,
                    }
                elif storage_type_str == "Double":
                    self.instances_param_dict[instance_id_str][param_name] = {
                        "value": param.AsDouble(),
                        "type": storage_type_str,
                    }
                elif storage_type_str == "Integer":
                    self.instances_param_dict[instance_id_str][param_name] = {
                        "value": param.AsInteger(),
                        "type": storage_type_str,
                    }
                elif storage_type_str == "ElementId":
                    self.instances_param_dict[instance_id_str][param_name] = {
                        "value": param.AsElementId().ToString(),
                        "type": storage_type_str,
                    }
                else:
                    self.instances_param_dict[instance_id_str][param_name] = {
                        "value": param.AsValueString(),
                        "type": storage_type_str,
                    }

        self.ex_event_file.set_key_value(
            "instances_param_dict", self.instances_param_dict
        )

        self.change_dialog_text_according_to_step()

    @property
    def step(self):
        return self._step

    @step.setter
    def step(self, value):
        self._step = value
        self.change_dialog_text_according_to_step()

    def change_dialog_text_according_to_step(self):
        self.StaticTextBlock.Text = self.messages[self.step]
        self.ExecuteCurrentStepBtn.Content = self.button_contents[self.step]

    def execute_current_step_btn_click(self, sender, e):
        if self.step == 0:
            rename_current_family_event.Raise()
        elif self.step == 1:
            load_new_family_event.Raise()
        elif self.step == 2:
            change_family_symbol_event.Raise()
        elif self.step == 3:
            restore_parameters_event.Raise()
        elif self.step == 4:
            delete_old_family_event.Raise()
        else:
            self.Close()
            return

        self.step += 1
