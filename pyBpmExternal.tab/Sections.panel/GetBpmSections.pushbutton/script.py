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

from Autodesk.Revit.DB import Transaction, FilteredElementCollector, RevitLinkInstance, ViewType, BuiltInParameter, ViewSection, ViewFamilyType, BoundingBoxXYZ, Transform, XYZ

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
    # Create a section whose view volume corresponds geometrically with the specified sectionBox. The view direction of the resulting section will be sectionBox.Transform.BasisZ and the up direction will be sectionBox.Transform.BasisY. The right hand direction will be computed so that (right, up, view direction) form a left handed coordinate system. The resulting view will be cropped, and far clipping will be active. The crop region will correspond to the projections of BoundingBoxXYZ.Min and BoundingBoxXYZ.Max onto the view's cut plane. The far clip distance will be equal to the difference of the z-coordinates of BoundingBoxXYZ.Min and BoundingBoxXYZ.Max. The new section ViewSection will receive a unique view name.

    # An example of how to create a section view from a wall with c#:
    # XYZ p = line.get_EndPoint( 0 );
    # XYZ q = line.get_EndPoint( 1 );
    # XYZ v = q - p;
 
    # BoundingBoxXYZ bb = wall.get_BoundingBox( null );
    # double minZ = bb.Min.Z;
    # double maxZ = bb.Max.Z;
 
    # double w = v.GetLength();
    # double h = maxZ - minZ;
    # double d = wall.WallType.Width;
    # double offset = 0.1 * w;
 
    # XYZ min = new XYZ( -w, minZ - offset, -offset );
    # XYZ max = new XYZ( w, maxZ + offset, 0 );
 
    # XYZ midpoint = p + 0.5 * v;
    # XYZ walldir = v.Normalize();
    # XYZ up = XYZ.BasisZ;
    # XYZ viewdir = walldir.CrossProduct( up );
 
    # Transform t = Transform.Identity;
    # t.Origin = midpoint;
    # t.BasisX = walldir;
    # t.BasisY = up;
    # t.BasisZ = viewdir;
 
    # BoundingBoxXYZ sectionBox = new BoundingBoxXYZ();
    # sectionBox.Transform = t;
    # sectionBox.Min = min;
    # sectionBox.Max = max;

    view_direction = -1 * transform.OfVector(section.ViewDirection)
    up_direction = transform.OfVector(section.UpDirection)
    right_direction = -1 * transform.OfVector(section.RightDirection)

    view_crop_region_CurveLoopIterator  = section.GetCropRegionShapeManager().GetCropShape()[0].GetCurveLoopIterator()
    view_crop_region_CurveLoopIterator.MoveNext()
    point1 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)
    view_crop_region_CurveLoopIterator.MoveNext()
    point2 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)
    view_crop_region_CurveLoopIterator.MoveNext()
    point3 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)
    view_crop_region_CurveLoopIterator.MoveNext()
    point4 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)

    point1 = transform.OfPoint(point1)
    point2 = transform.OfPoint(point2)
    point3 = transform.OfPoint(point3)
    point4 = transform.OfPoint(point4)

    points = [point1, point2, point3, point4]

    section_height = None
    section_length = None
    for i in range(len(points)):
        next = i + 1 if i < len(points) - 1 else 0
        v = points[next] - points[i]
        if not section_height and v.DotProduct(right_direction) == 0:
            section_height = v.GetLength()
        if not section_length and v.DotProduct(up_direction) == 0:
            section_length = v.GetLength()

    if not section_height or not section_length:
        alert("Couldn't calculate section height and length.")
        return

    section_far_clip = section.get_Parameter(BuiltInParameter.VIEWER_BOUND_OFFSET_FAR).AsDouble()

    xyz_min = XYZ(-0.5 * section_length, -0.5 * section_height, -0.5 * section_far_clip)
    xyz_max = XYZ(0.5 * section_length, 0.5 * section_height, 0.5 * section_far_clip)

    mid_point = (point1 + point2 + point3 + point4) / 4
    mid_point = mid_point + 0.5 * section_far_clip * view_direction
    
    section_box = BoundingBoxXYZ()
    section_box.Enabled = True

    t = Transform.Identity
    t.Origin = mid_point
    t.BasisZ = view_direction
    t.BasisY = up_direction
    t.BasisX = right_direction

    section_box.Transform = t
    section_box.Min = xyz_min
    section_box.Max = xyz_max

    return ViewSection.CreateSection(doc, viewFamilyTypeId, section_box)

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
    new_view = create_section(selected_section, selected_viewFamilyType.Id, comp_link.GetTotalTransform())
    t.Commit()

    if new_view:
        uidoc.ActiveView = new_view

run()
