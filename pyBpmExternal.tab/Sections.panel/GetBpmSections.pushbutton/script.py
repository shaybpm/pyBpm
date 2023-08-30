# -*- coding: utf-8 -*-
""" Create selected section from the Bpm suggested sections. """
__title__ = 'Get Bpm\nSections'
__author__ = 'Eyal Sinay'

# ------------------------------------------------------------

import clr
clr.AddReference('RevitAPI')
clr.AddReferenceByPartialName('PresentationCore')
clr.AddReferenceByPartialName('AdWindows')
clr.AddReferenceByPartialName("PresentationFramework")
clr.AddReferenceByPartialName('System')
clr.AddReferenceByPartialName('System.Windows.Forms')

# from System.Collections.Generic import List

from Autodesk.Revit.DB import Transaction, FilteredElementCollector, RevitLinkInstance, ViewType, BuiltInParameter, ViewSection, ViewFamilyType

from Autodesk.Revit.UI import TaskDialog

from pyrevit import forms

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'lib'))
import RevitUtils, pyUtils

max_elements = 5
gdict = globals()
uiapp = __revit__
uidoc = uiapp.ActiveUIDocument
if uidoc:
    doc = uiapp.ActiveUIDocument.Document

transaction_name = 'BPM | Get Bpm Section'
def alert(msg):
    TaskDialog.Show(transaction_name, msg)

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

def get_all_section_viewFamilyTypes():
	all_viewFamilyTypes = FilteredElementCollector(doc).OfClass(ViewFamilyType).ToElements()
	section_viewFamilyTypes = []
	for viewFamilyType in all_viewFamilyTypes:
		if viewFamilyType.FamilyName == "Section":
			section_viewFamilyTypes.append(viewFamilyType)
	return section_viewFamilyTypes

def create_section(section, viewFamilyTypeId, transform):
	section_bbox = section.get_BoundingBox(None)
	section_bbox.Transform = transform
	ViewSection.CreateSection(doc, viewFamilyTypeId, section_bbox)

def run():
    comp_link = get_comp_link()
    if not comp_link:
        alert("The Compilation mode link is not loaded.")
        return
    comp_doc = comp_link.GetLinkDocument()
    selected_section = forms.select_views(title='Select Plans', button_name='Copy', width=500, multiple=False, filterfunc=is_su_sec, doc=comp_doc)
    
    if not selected_section:
        return
    
    section_viewFamilyTypes = get_all_section_viewFamilyTypes()
    section_viewFamilyTypes_names = [RevitUtils.getElementName(viewFamilyType) for viewFamilyType in section_viewFamilyTypes]
    selected_viewFamilyType_str = forms.SelectFromList.show(section_viewFamilyTypes_names, title='Select Section Type', button_name='Select', multiselect=False)
    if not selected_viewFamilyType_str:
        return
    
    selected_viewFamilyType = pyUtils.findInList(section_viewFamilyTypes, lambda viewFamilyType: RevitUtils.getElementName(viewFamilyType) == selected_viewFamilyType_str)
    
    t = Transaction(doc, transaction_name)
    t.Start()
    create_section(selected_section, selected_viewFamilyType.Id, comp_link.GetTotalTransform())
    t.Commit()

run()
