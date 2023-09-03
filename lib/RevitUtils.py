uiapp = __revit__
uidoc = uiapp.ActiveUIDocument
if uidoc:
    doc = uiapp.ActiveUIDocument.Document

revit_version = int(doc.Application.VersionNumber)

def getElementName(element):
	from Autodesk.Revit.DB import Element
	return Element.Name.__get__(element)

def convertRevitNumToCm(num):
	from Autodesk.Revit.DB import UnitUtils
	if revit_version < 2021:
		from Autodesk.Revit.DB import DisplayUnitType
		return UnitUtils.ConvertFromInternalUnits(num, DisplayUnitType.DUT_CENTIMETERS)
	else:
		from Autodesk.Revit.DB import UnitTypeId
		return UnitUtils.ConvertFromInternalUnits(num, UnitTypeId.Centimeters)
	
def convertCmToRevitNum(cm):
	from Autodesk.Revit.DB import UnitUtils
	if revit_version < 2021:
		from Autodesk.Revit.DB import DisplayUnitType
		return UnitUtils.ConvertToInternalUnits(cm, DisplayUnitType.DUT_CENTIMETERS)
	else:
		from Autodesk.Revit.DB import UnitTypeId
		return UnitUtils.ConvertToInternalUnits(cm, UnitTypeId.Centimeters)
