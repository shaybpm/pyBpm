# -*- coding: utf-8 -*-
import json


def get_json_from_file(path):
    f = open(path, "r")
    res = json.load(f)
    f.close()
    return res


def findInList(list, cb_function):
    for item in list:
        if cb_function(item):
            return item
    return None


def is_close(a, b, rel_tol=1e-09, abs_tol=0.0):
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


def env_mode():
    if "Software_Development\RevitDevelopment\PyRevitBpm" in __file__:
        return "dev"
    else:
        return "prod"
