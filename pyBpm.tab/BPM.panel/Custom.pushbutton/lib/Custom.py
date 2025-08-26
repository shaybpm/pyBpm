# -*- coding: utf-8 -*-

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "BondsViewer"))
sys.path.append(os.path.join(os.path.dirname(__file__), "GetBpmAcViews"))
from BondsViewer import bonds_viewer  # type: ignore
from GetBpmAcViews import get_bpm_ac_view_templates  # type: ignore


def common_scripts():
    """Return a list of common scripts."""
    return [
        "Bonds Viewer",
        "Get BPM AC View Templates"
    ]


def custom_scripts(doc):
    """Return a list of scripts by project."""
    return []


def run_by_name(name, uidoc):
    """Run a script by its name."""
    if name == "Bonds Viewer":
        bonds_viewer(uidoc)
    elif name == "Get BPM AC View Templates":
        get_bpm_ac_view_templates(uidoc)
    else:
        raise ValueError("Script '{}' not found.".format(name))
