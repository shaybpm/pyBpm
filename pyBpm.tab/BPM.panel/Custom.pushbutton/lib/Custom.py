# -*- coding: utf-8 -*-

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "BondsViewer"))
from BondsViewer import bonds_viewer  # type: ignore


def common_scripts():
    """Return a list of common scripts."""
    return [
        "Bonds Viewer",
    ]


def custom_scripts(doc):
    """Return a list of scripts by project."""
    return []


def run_by_name(name, uidoc):
    """Run a script by its name."""
    if name == "Bonds Viewer":
        bonds_viewer(uidoc)
    else:
        raise ValueError("Script '{}' not found.".format(name))
