# -*- coding: utf-8 -*-

import json, os
from pyrevit.script import get_data_file

# get_data_file:
# provide a unique file id and file extension
# Method will return full path of the data file

class LocalUserInputs:
    def __init__(self, file_name, defaults=None):
        """Utility class to manage local user inputs stored in a JSON file.
        This class handles reading and writing user inputs to a specified JSON file.

        Args:
            file_name (str): The name of the JSON file where user inputs are stored.
            defaults (dict, optional): Default values for user inputs. If not provided, an empty dictionary is used.
        """
        self.file_name = file_name
        self.defaults = defaults if defaults is not None else {}
        self.data = {}
        self.file_path = get_data_file(self.file_name, "json")
        
        self.load_inputs()
        
    def load_inputs(self):
        if not os.path.exists(self.file_path):
            self.data = self.defaults
            return
        
        try:
            with open(self.file_path, 'r') as f:
                self.data = json.load(f)
        except ValueError:
            # A corrupt file (truncated by an older save_inputs, or by a crash
            # mid-write) must not lock the tool out - start over from defaults.
            self.data = {}
        for key, value in self.defaults.items():
            if key not in self.data:
                self.data[key] = value


    def save_inputs(self):
        """Saves the current user inputs to the JSON file."""
        # Serialize before opening the file, and keep the output ASCII (\uXXXX):
        # IronPython's text-mode file encodes as 'ascii' on buffer flush, so a
        # non-ASCII char used to raise mid-write and truncate the file at 8 KB.
        content = json.dumps(self.data, indent=4)
        with open(self.file_path, 'w') as f:
            f.write(content)