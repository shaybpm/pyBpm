def getElementName(element):
	from Autodesk.Revit.DB import Element
	return Element.Name.__get__(element)
