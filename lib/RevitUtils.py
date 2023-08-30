from Autodesk.Revit.DB import Element

def getElementName(element):
	return Element.Name.__get__(element)
