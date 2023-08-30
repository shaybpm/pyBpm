# -*- coding: utf-8 -*-
""" Copy Bpm suggest sections to the current project. """
__title__ = 'Copy Bpm\nSections'
__author__ = 'Eyal Sinay'

# ------------------------------------------------------------

import clr
clr.AddReference('RevitAPI')
clr.AddReferenceByPartialName('PresentationCore')
clr.AddReferenceByPartialName('AdWindows')
clr.AddReferenceByPartialName("PresentationFramework")
clr.AddReferenceByPartialName('System')
clr.AddReferenceByPartialName('System.Windows.Forms')

from Autodesk.Revit.DB import Transaction, FilteredElementCollector, RevitLinkInstance, ViewType
from Autodesk.Revit.UI import TaskDialog

from pyrevit import forms

max_elements = 5
gdict = globals()
uiapp = __revit__
uidoc = uiapp.ActiveUIDocument
if uidoc:
    doc = uiapp.ActiveUIDocument.Document

def alert(msg):
    TaskDialog.Show('BPM - Copy Bpm Sections', msg)

# ------------------------------------------------------------

def get_all_links():
    return FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()

def get_comp_doc():
    all_links = get_all_links()
    for link in all_links:
        if "COMP" in link.Name:
              return link.GetLinkDocument()

def is_su_sec(view):
    if not view.ViewType:
        return False

    if not view.ViewType == ViewType.Section:
        return False

    if not "SU" in view.Name:
        return False

    return True

def run():
    selected_sections = forms.select_views(title='Select Plans', button_name='Copy', width=500, multiple=True, filterfunc=is_su_sec, doc=get_comp_doc())

run()
