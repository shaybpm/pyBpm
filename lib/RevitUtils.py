from Autodesk.Revit.DB import Element, BoundingBoxXYZ, BuiltInParameter

def getElementName(element):
	return Element.Name.__get__(element)

def isMaxMin(max, min):
    return max.X > min.X and max.Y > min.Y and max.Z > min.Z

def GetSecBoundingBox(view, transform = None):
	view_direction = view.ViewDirection if not transform else transform.OfVector(view.ViewDirection)
	view_far_clip_offset = view.get_Parameter(BuiltInParameter.VIEWER_BOUND_OFFSET_FAR).AsDouble()
	offset_vector = -1 * view_direction * view_far_clip_offset

	view_crop_region_CurveLoopIterator  = view.GetCropRegionShapeManager().GetCropShape()[0].GetCurveLoopIterator()
	view_crop_region_CurveLoopIterator.MoveNext()
	point1 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)
	view_crop_region_CurveLoopIterator.MoveNext()
	point2 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)
	view_crop_region_CurveLoopIterator.MoveNext()
	point3 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)
	view_crop_region_CurveLoopIterator.MoveNext()
	point4 = view_crop_region_CurveLoopIterator.Current.GetEndPoint(0)

	if transform:
		point1 = transform.OfPoint(point1)
		point2 = transform.OfPoint(point2)
		point3 = transform.OfPoint(point3)
		point4 = transform.OfPoint(point4)

	bb_box = BoundingBoxXYZ()
	if (isMaxMin(point1, point3.Add(offset_vector))):
		bb_box.Max = point1
		bb_box.Min = point3.Add(offset_vector)
		return bb_box
	elif (isMaxMin(point1.Add(offset_vector), point3)):
		bb_box.Max = point1.Add(offset_vector)
		bb_box.Min = point3
		return bb_box
	elif (isMaxMin(point3, point1.Add(offset_vector))):
		bb_box.Max = point3
		bb_box.Min = point1.Add(offset_vector)
		return bb_box
	elif (isMaxMin(point3.Add(offset_vector), point1)):
		bb_box.Max = point3.Add(offset_vector)
		bb_box.Min = point1
		return bb_box
	elif (isMaxMin(point2, point4.Add(offset_vector))):
		bb_box.Max = point2
		bb_box.Min = point4.Add(offset_vector)
		return bb_box
	elif (isMaxMin(point2.Add(offset_vector), point4)):
		bb_box.Max = point2.Add(offset_vector)
		bb_box.Min = point4
		return bb_box
	elif (isMaxMin(point4, point2.Add(offset_vector))):
		bb_box.Max = point4
		bb_box.Min = point2.Add(offset_vector)
		return bb_box
	elif (isMaxMin(point4.Add(offset_vector), point2)):
		bb_box.Max = point4.Add(offset_vector)
		bb_box.Min = point2
		return bb_box
	else:
		print('No bounding box found')
		return None
