import clr
clr.AddReference('RevitAPI')
clr.AddReferenceByPartialName('PresentationCore')
clr.AddReferenceByPartialName('AdWindows')
clr.AddReferenceByPartialName("PresentationFramework")
clr.AddReferenceByPartialName('System')
clr.AddReferenceByPartialName('System.Windows.Forms')

from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory, BuiltInParameter

# ------------------------------------------------------------

def get_all_openings(doc):
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

def is_floor(opening):
    """ Returns True if the host of the opening is a floor, else returns False.
     We don't use the host property because sometimes the connection between the opening and the host is broken. """
    param__Elevation_from_Level = opening.LookupParameter('Elevation from Level')
    if not param__Elevation_from_Level:
        return False
    if param__Elevation_from_Level.IsReadOnly:
        return True
    else:
        return False
    
def set_mep_not_required_param(doc, opening, print_warnings = True):
    """ Get the schedule level parameter and check if it is match to the opening instance in the model. If it is, set the MEP - Not Required parameter to true, else set it to false. """
    param__mep_not_required = opening.LookupParameter('MEP - Not Required')
    if not param__mep_not_required:
        if print_warnings:
            print('WARNING: No MEP - Not Required parameter found. Opening ID: {}'.format(opening.Id))
        return "WARNING"
    param__schedule_level = opening.get_Parameter(BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM)
    id__schedule_level = param__schedule_level.AsElementId()
    if id__schedule_level.IntegerValue == -1:
        param__mep_not_required.Set(0)
        if print_warnings:
            print('WARNING: No Schedule Level parameter found. Opening ID: {}'.format(opening.Id))
        return "WARNING"

    all_floors = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Floors).WhereElementIsNotElementType().ToElements()
     
    if not is_floor(opening):
        all_floors = [floor for floor in all_floors if floor.get_BoundingBox(None).Min.Z <= opening.Location.Point.Z]
    
    if len(all_floors) == 0:
        param__mep_not_required.Set(0)
        return "OK"

    opening_location_point_z = opening.Location.Point.Z
    target_floor = all_floors[0]
    target_floor_location_point_z = target_floor.get_BoundingBox(None).Min.Z
    for floor in all_floors:
        floor_location_point_z = floor.get_BoundingBox(None).Min.Z
        if abs(floor_location_point_z - opening_location_point_z) < abs(target_floor_location_point_z - opening_location_point_z):
            target_floor = floor
            target_floor_location_point_z = floor_location_point_z

    if target_floor.LevelId == id__schedule_level:
        param__mep_not_required.Set(1)
    else:
        param__mep_not_required.Set(0)
    return "OK"

def set_comments(opening, print_warnings = True):
    """ Sets the comments parameter to 'F' if the host of the opening is a floor, and 'nF' if not. """
    para__comments = opening.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
    if not para__comments:
        if print_warnings:
            print('WARNING: No Comments parameter found. Opening ID: {}'.format(opening.Id))
        return "WARNING"
    if is_floor(opening):
        para__comments.Set('F')
    else:
        para__comments.Set('nF')
    return "OK"

def set_elevation_params(doc, opening, print_warnings = True):
    """ Sets the elevation parameters: 'Opening Elevation' and 'Opening Absolute Level'... """
    project_base_point = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_ProjectBasePoint).WhereElementIsNotElementType().ToElements()[0]
    project_base_point_elevation = project_base_point.get_Parameter(BuiltInParameter.BASEPOINT_ELEVATION_PARAM).AsDouble()
    opening_location_point_z = opening.Location.Point.Z
    param__opening_elevation = opening.LookupParameter('Opening Elevation')
    param__opening_absolute_level = opening.LookupParameter('Opening Absolute Level')
    if not param__opening_elevation or not param__opening_absolute_level:
        if print_warnings:
            print('WARNING: No Opening Elevation or Opening Absolute Level parameter found. Opening ID: {}'.format(opening.Id))
        return "WARNING"
    param__opening_elevation.Set(opening_location_point_z)
    param__opening_absolute_level.Set(opening_location_point_z + project_base_point_elevation)
    return "OK"

def set_ref_level_and_mid_elevation(opening, print_warnings = True):
    """ Sets the parameter '##Reference Level' to get the value in that in the parameter 'Schedule Level', and the parameter '##Middle Elevation' to get the value that in the parameter: 'Elevation from Level' """
    param__schedule_level = opening.get_Parameter(BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM)
    param__reference_level = opening.LookupParameter('##Reference Level')
    param__elevation_from_level = opening.LookupParameter('Elevation from Level')
    param__middle_elevation = opening.LookupParameter('##Middle Elevation')
    if not param__schedule_level or not param__reference_level or not param__elevation_from_level or not param__middle_elevation:
        if print_warnings:
            print('WARNING: No Schedule Level or ##Reference Level or Elevation from Level or ##Middle Elevation parameter found. Opening ID: {}'.format(opening.Id))
        return "WARNING"
    param__reference_level.Set(param__schedule_level.AsValueString())
    param__middle_elevation.Set(param__elevation_from_level.AsDouble())
    return "OK"

def opening_number_generator(doc):
    """ Generates a number for the opening. """
    all_openings = get_all_openings(doc)
    all_existing_numbers = []
    for opening in all_openings:
        param__mark = opening.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)
        if param__mark.AsString() and param__mark.AsString().isdigit():
            all_existing_numbers.append(int(param__mark.AsString()))
    
    number = 1
    while number in all_existing_numbers:
        number += 1
    return str(number)

def set_mark(doc, opening, print_warnings = True):
    """ Sets the Mark parameter to opening number. """
    param__mark = opening.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)
    if not param__mark:
        if print_warnings:
            print('WARNING: No Mark parameter found. Opening ID: {}'.format(opening.Id))
        return "WARNING"
    if param__mark.AsString() and param__mark.AsString().isdigit():
        return "OK"
    num = opening_number_generator(doc)
    param__mark.Set(num)
    return "OK"

def execute_all_functions(doc, opening, print_warnings = True):
    results = set_mep_not_required_param(doc, opening, print_warnings)
    results = set_comments(opening, print_warnings)
    results = set_elevation_params(doc, opening, print_warnings)
    results = set_ref_level_and_mid_elevation(opening, print_warnings)
    results = set_mark(doc, opening, print_warnings)
    if "WARNING" in results:
        return "WARNING"
    return "OK"
