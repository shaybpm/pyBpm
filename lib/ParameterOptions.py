# -*- coding: utf-8 -*-
"""Build the list of valid options for an ElementId-storage parameter.

Detection is by data-type / target-class, NOT by hardcoding every
BuiltInParameter (one mechanism catches a whole family of params, e.g. all 11
Material params via SpecTypeId.Reference.Material). Only parameters whose option
set we know for certain are handled; anything else returns None so the caller
leaves it untouched. See QuickParamEdit_ElementId_Params.md for the research.
"""

from RevitUtils import getElementName, getElementIdValue
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    Material,
    FillPatternElement,
    LinePatternElement,
    ImageType,
    Level,
    Phase,
    PhaseFilter,
    ElementType,
    BuiltInParameter,
    FilteredWorksetCollector,
    WorksetKind,
    StorageType,
    SpecTypeId,
    ElementId,
)

try:
    from Autodesk.Revit.DB.Electrical import LoadClassification
except Exception:
    LoadClassification = None


class ParameterOption:
    def __init__(self, label, value):
        self.label = label  # type: str
        self.value = value  # type: ElementId | int


# --- Reference-spec TypeIds, read at runtime so they match the Revit version ---
# (the version suffix in the TypeId string changes between releases).
def _ref_tid(name):
    try:
        return getattr(SpecTypeId.Reference, name).TypeId
    except Exception:
        return None


_MATERIAL_TID = _ref_tid("Material")
_FILLPATTERN_TID = _ref_tid("FillPattern")
_IMAGE_TID = _ref_tid("Image")
_LOADCLASS_TID = _ref_tid("LoadClassification")


def _bip_set(names):
    """Build a set of BuiltInParameter members, skipping any missing in this version."""
    result = set()
    for n in names:
        member = getattr(BuiltInParameter, n, None)
        if member is not None:
            result.add(member)
    return result


# Level params: empirical detection (value points to a Level) covers most, but
# these are listed so an EMPTY value still resolves to "all levels".
_LEVEL_BIPS = _bip_set([
    "LEVEL_PARAM",
    "FAMILY_LEVEL_PARAM",
    "INSTANCE_REFERENCE_LEVEL_PARAM",
    "INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM",
    "SCHEDULE_LEVEL_PARAM",
    "RBS_START_LEVEL_PARAM",
    "RBS_END_LEVEL_PARAM",
    "WALL_BASE_CONSTRAINT",
    "WALL_HEIGHT_TYPE",
    "LEVEL_UP_TO_LEVEL",
])

# The element's own identity (type/family/category) - NOT a referenced-type
# picker. Changing an element's type belongs to ChangeTypeId, so skip these even
# though their value points to an ElementType.
_SKIP_BIPS = _bip_set([
    "ELEM_TYPE_PARAM",
    "ELEM_FAMILY_PARAM",
    "ELEM_FAMILY_AND_TYPE_PARAM",
    "SYMBOL_ID_PARAM",
    "ELEM_CATEGORY_PARAM",
    "ELEM_CATEGORY_PARAM_MT",
    "DESIGN_OPTION_ID",
    "HOST_ID_PARAM",
])


# --------------------------------------------------------------------------
# Option builders
# --------------------------------------------------------------------------

def _type_label(element):
    """'Family : Type' when a family name exists, else the element name."""
    name = getElementName(element)
    family = None
    try:
        family = element.FamilyName
    except Exception:
        family = None
    if family:
        return u"{0} : {1}".format(family, name)
    return name


def _for_class(doc, element_class):
    options = []
    try:
        elements = FilteredElementCollector(doc).OfClass(element_class)
    except Exception:
        return None
    for element in elements:
        options.append(ParameterOption(getElementName(element), element.Id))
    return options


def _for_category_types(doc, category):
    """All element types of a category (for FamilySymbol-style type pickers)."""
    options = []
    try:
        elements = (
            FilteredElementCollector(doc)
            .OfCategoryId(category.Id)
            .WhereElementIsElementType()
        )
    except Exception:
        return None
    for element in elements:
        options.append(ParameterOption(_type_label(element), element.Id))
    return options


def _for_element_type(doc, target_type):
    """Type picker, derived empirically from the current value's type."""
    category = None
    try:
        category = target_type.Category
    except Exception:
        category = None
    if category is not None:
        opts = _for_category_types(doc, category)
        if opts is not None:
            return opts
    # No category (e.g. TextNoteType, DimensionType) -> collect by exact class.
    try:
        return _for_class(doc, target_type.GetType())
    except Exception:
        return None


def _for_levels(doc):
    options = []
    levels = FilteredElementCollector(doc).OfClass(Level)
    for level in levels:
        options.append(ParameterOption(getElementName(level), level.Id))
    return options


def _for_phases(doc, include_none):
    options = []
    if include_none:
        options.append(ParameterOption(u"None", ElementId.InvalidElementId))
    for phase in doc.Phases:
        options.append(ParameterOption(phase.Name, phase.Id))
    return options


def _for_worksets(doc):
    options = []
    worksets = (
        FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset).ToWorksets()
    )
    for workset in worksets:
        options.append(ParameterOption(workset.Name, workset.Id.IntegerValue))
    return options


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _get_bip(parameter):
    """BuiltInParameter member, or None for shared/project params."""
    try:
        member = getattr(parameter.Definition, "BuiltInParameter", None)
        if member is None or member == BuiltInParameter.INVALID:
            return None
        return member
    except Exception:
        return None


def _data_type_id(parameter):
    try:
        return parameter.Definition.GetDataType().TypeId
    except Exception:
        return None


def _resolve_target(doc, parameter):
    """The element the parameter currently points to, or None if empty/invalid."""
    try:
        value_id = parameter.AsElementId()
        if value_id is not None and getElementIdValue(doc, value_id) > 0:
            return doc.GetElement(value_id)
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------

def get_parameter_options(doc, parameter):
    """Return a list of ParameterOption for an ElementId/Workset parameter, or
    None when the parameter is not one we can resolve options for.

    Detection order (earlier tiers work even when the current value is empty):
      1. Workset            (BIP, StorageType.Integer)
      2. Phase              (BIP)
      3. Reference specs    (data-type: Material / FillPattern / Image / LoadClassification)
      4. Level              (BIP)
      5. Skip self-identity (ELEM_TYPE/FAMILY/CATEGORY ...)
      6. Empirical          (by the current value's target class)
    """
    bip = _get_bip(parameter)

    # 1) Workset - StorageType is Integer, so handle before the ElementId guard.
    if bip is not None and bip == getattr(BuiltInParameter, "ELEM_PARTITION_PARAM", None):
        return _for_worksets(doc)

    # Everything below is ElementId-storage only.
    try:
        if parameter.StorageType != StorageType.ElementId:
            return None
    except Exception:
        return None

    # 2) Phase by BIP (works with an empty value).
    if bip is not None:
        if bip == getattr(BuiltInParameter, "PHASE_CREATED", None):
            return _for_phases(doc, include_none=False)
        if bip == getattr(BuiltInParameter, "PHASE_DEMOLISHED", None):
            return _for_phases(doc, include_none=True)

    # 3) Reference-spec data types (work with an empty value).
    dt_id = _data_type_id(parameter)
    if dt_id is not None:
        if dt_id == _MATERIAL_TID:
            return _for_class(doc, Material)
        if dt_id == _FILLPATTERN_TID:
            return _for_class(doc, FillPatternElement)
        if dt_id == _IMAGE_TID:
            return _for_class(doc, ImageType)
        if dt_id == _LOADCLASS_TID and LoadClassification is not None:
            return _for_class(doc, LoadClassification)

    # 4) Known Level parameters by BIP (works with an empty value).
    if bip is not None and bip in _LEVEL_BIPS:
        return _for_levels(doc)

    # 5) Skip the element's own identity type/family/category.
    if bip is not None and bip in _SKIP_BIPS:
        return None

    # 6) Empirical - classify by what the current value points to.
    target = _resolve_target(doc, parameter)
    if target is not None:
        if isinstance(target, Level):
            return _for_levels(doc)
        if isinstance(target, Phase):
            return _for_phases(doc, include_none=False)
        if isinstance(target, PhaseFilter):
            return _for_class(doc, PhaseFilter)
        if isinstance(target, FillPatternElement):
            return _for_class(doc, FillPatternElement)
        if isinstance(target, LinePatternElement):
            return _for_class(doc, LinePatternElement)
        if isinstance(target, ElementType):
            return _for_element_type(doc, target)

    return None
