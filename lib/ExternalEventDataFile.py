# -*- coding: utf-8 -*-

import os, json
from pyrevit.script import get_instance_data_file, get_bundle_name


class ExternalEventDataFile:
    def __init__(self, doc):
        model_guid = (
            doc.GetCloudModelPath().GetModelGUID().ToString()
            if doc.IsModelInCloud
            else doc.Title
        )
        bundle_name = get_bundle_name()
        self.file_path = get_instance_data_file("{}_{}".format(bundle_name, model_guid))

    def get_data(self):
        if not os.path.exists(self.file_path):
            return {}
        with open(self.file_path, "r") as file:
            data = json.load(file)
        return data

    def get_key_value(self, key):
        data = self.get_data()
        return data.get(key)

    def set_data(self, data):
        with open(self.file_path, "w") as file:
            json.dump(data, file)

    def set_key_value(self, key, value):
        data = self.get_data()
        data[key] = value
        self.set_data(data)
