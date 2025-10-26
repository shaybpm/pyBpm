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


def safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_unique_file_name(folder, base_name, extension):
    import os

    file_path = os.path.join(folder, "{}.{}".format(base_name, extension))
    if not os.path.exists(file_path):
        return file_path
    i = 1
    max_tries = 1000
    while i < max_tries:
        file_path = os.path.join(folder, "{}_{}.{}".format(base_name, i, extension))
        if not os.path.exists(file_path):
            return file_path
        i += 1
    raise Exception(
        "Could not find a unique file name after {} tries".format(max_tries)
    )


def sanitize_filename(name):
    import re

    invalid_chars_pattern = r'[<>:"/\\|?*\x00-\x1F]'
    sanitized_name = re.sub(invalid_chars_pattern, "_", name).strip().strip(".")

    reserved = {"CON", "PRN", "AUX", "NUL"}
    if sanitized_name.upper() in reserved or re.match(
        r"^(COM|LPT)[1-9]$", sanitized_name.upper()
    ):
        sanitized_name = "_" + sanitized_name

    sanitized_name = re.sub(r"_+", "_", sanitized_name)  # optional
    sanitized_name = sanitized_name[:255] or "_unnamed"  # optional

    return sanitized_name
