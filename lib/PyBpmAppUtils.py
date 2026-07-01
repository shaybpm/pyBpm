# -*- coding: utf-8 -*-
import os
import pyUtils
import Config
import HttpRequest


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


def get_current_version():
    local_extension_path = os.path.join(Config.root_path, "extension.json")
    local_extension_file = pyUtils.get_json_from_file(local_extension_path)
    current_version = local_extension_file["version"]
    return current_version


def get_latest_version():
    github_extension_file = HttpRequest.get(Config.extension_json_url)
    latest_version = github_extension_file["version"]
    return latest_version


def has_new_version():
    return get_current_version() != get_latest_version()
