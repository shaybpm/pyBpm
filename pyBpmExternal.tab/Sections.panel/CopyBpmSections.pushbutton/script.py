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

from System.Collections.Generic import List

from Autodesk.Revit.DB import Transaction, FilteredElementCollector, RevitLinkInstance, ViewType, ElementTransformUtils, ElementId, BuiltInParameter, CopyPasteOptions

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

def get_comp_link():
    all_links = FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()
    for link in all_links:
        if "COMP" in link.Name:
              return link

def is_su_sec(view):
	if not view.ViewType:
		return False

	if not view.ViewType == ViewType.Section:
		return False

	if not "SU" in view.Name:
		return False
	
	viewport_sheet_number = view.get_Parameter(BuiltInParameter.VIEWPORT_SHEET_NUMBER)
	if not viewport_sheet_number.AsString():
		return False

	return True

def run():
    comp_link = get_comp_link()
    if not comp_link:
        alert("The Compilation mode link is not loaded.")
        return
    comp_doc = comp_link.GetLinkDocument()
    selected_sections = forms.select_views(title='Select Plans', button_name='Copy', width=500, multiple=True, filterfunc=is_su_sec, doc=comp_doc)
    if not selected_sections or len(selected_sections) == 0:
        return
    
    opts = CopyPasteOptions()
    transform = comp_link.GetTotalTransform()
    ilSection = List[ElementId]([x.Id for x in selected_sections])
    
    t = Transaction(doc, 'BPM | Copy Bpm Sections')
    t.Start()
    ElementTransformUtils.CopyElements(comp_doc, ilSection, doc, transform, opts)
    t.Commit()

run()
