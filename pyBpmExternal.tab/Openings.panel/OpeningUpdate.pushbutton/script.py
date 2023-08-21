""" This script iterates over all the openings (Generic Model from the BPM library) and dose the following:
- Copies the Elevation to a taggable parameter (useful in versions 20+21).
- Copies the Reference Level to a taggable parameter.
- Sets Mark to opening it is missing.
- Defines whether the opening is located in the floor or not.
- Calculates the projected height of the opening.
- Calculates the absolute height of the opening. """
__title__ = 'Opening\nUpdate'
__author__ = 'Eyal Sinay'

# ------------------------------

import clr
clr.AddReference('RevitAPI')
clr.AddReferenceByPartialName('PresentationCore')
clr.AddReferenceByPartialName('AdWindows')
clr.AddReferenceByPartialName("PresentationFramework")
clr.AddReferenceByPartialName('System')
clr.AddReferenceByPartialName('System.Windows.Forms')

from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory, Transaction, BuiltInParameter
from Autodesk.Revit.UI import TaskDialog

# from System.Collections.Generic import List

# import Autodesk.Windows as aw

max_elements = 5
gdict = globals()
uiapp = __revit__
uidoc = uiapp.ActiveUIDocument
if uidoc:
    doc = uiapp.ActiveUIDocument.Document
    # selection = [doc.GetElement(x) for x in uidoc.Selection.GetElementIds()]
    # for idx, el in enumerate(selection):
    #     if idx < max_elements:
    #         gdict['e{}'.format(idx+1)] = el
    #     else:
    #         break

# alert function
def alert(msg):
    TaskDialog.Show('BPM - Opening Update', msg)

# ------------------------------------------------------------

def get_all_openings():
    """ Returns a list of all the openings in the model. """
    opening_names = [
        'Round Face Opening',
        'Rectangular Face Opening',
        'CIRC_FLOOR OPENING',
        'CIRC_WALL OPENING',
        'REC_FLOOR OPENING',
        'REC_WALL OPENING'
    ]
    openings = []
    generic_models = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_GenericModel).WhereElementIsNotElementType().ToElements()
    for gm in generic_models:
        if gm.Name in opening_names:
            openings.append(gm)
    return openings

def set_schedule_level(opening):
    """ Sets the Schedule Level parameter to the correct level. """
    all_levels = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Levels).WhereElementIsNotElementType().ToElements()
    all_levels_sorted = sorted(all_levels, key = lambda x: x.Elevation)
    all_levels_sorted_length = len(all_levels_sorted)
    opening_location_point_z = opening.Location.Point.Z
    param__schedule_level = opening.get_Parameter(BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM)
    if all_levels_sorted[0].Elevation >= opening_location_point_z:
        param__schedule_level.Set(all_levels_sorted[0].Id)
        return
    if all_levels_sorted[all_levels_sorted_length - 1].Elevation <= opening_location_point_z:
        param__schedule_level.Set(all_levels_sorted[all_levels_sorted_length - 1].Id)
        return
    for i in range(all_levels_sorted_length - 1):
        if all_levels_sorted[i].Elevation <= opening_location_point_z and all_levels_sorted[i + 1].Elevation > opening_location_point_z:
            param__schedule_level.Set(all_levels_sorted[i].Id)
            return
    print('No level found for opening: {}'.format(opening.Id))

def set_comments(opening):
    """ Sets the comments parameter to 'F' if the host of the opening is a floor, and 'nF' if not. """
    # ? Why not get the host and check its category?
    param__Elevation_from_Level = opening.LookupParameter('Elevation from Level')
    if not param__Elevation_from_Level:
        print('No Elevation from Level parameter found.')
        return
    if param__Elevation_from_Level.IsReadOnly:
        opening.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS).Set('F')
    else:
        opening.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS).Set('nF')

def set_elevation_params1(opening):
    """ Sets the elevation parameters: 'Opening Elevation' and 'Opening Absolute Level'... """
    pass

def set_elevation_params2(opening):
    """ Sets the elevation parameters: '#Elevation at Bottom' and '##Bottom Elevation'... """
    pass

def set_ref_level_and_mid_elevation(opening):
    """ Sets the parameters: '##Reference Level' and '##Middle Elevation'... """
    pass

def set_mark(opening):
    """ Sets the Mark parameter... """
    pass

def execute_all_functions(opening):
    set_schedule_level(opening)
    set_comments(opening)
    set_elevation_params1(opening)
    set_elevation_params2(opening)
    set_ref_level_and_mid_elevation(opening)

def run():
    all_openings = get_all_openings()
    if len(all_openings) == 0:
        alert('No openings found.')
        return
    
    t = Transaction(doc, 'BPM | Opening Update')
    t.Start()
    for opening in all_openings:
        execute_all_functions(opening)
    
    t.Commit()

run()
