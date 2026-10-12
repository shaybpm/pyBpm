# -*- coding: utf-8 -*-
""" Section coloring for Get Bpm Sections (T-0494).

Makes the origin of every system in a BPM section obvious at a glance:

    this model (the planner's own systems)  -> BLUE, per-element overrides
    the compilation link (the coordinator)  -> YELLOW, through a filter

Same mechanism as SecReport in the internal extension, with the roles
reversed (there the host IS the compilation model), and the color settings are
taken from it verbatim so both tools read the same way: blue = existing,
yellow = proposed.

Why a category-only filter works: a filter with categories and no rules
matches EVERY element of those categories in the view - the host's and the
link's alike - but an element override always wins over a filter override. So
painting the host's elements blue leaves exactly the link's elements yellow.
The consequence the planner must know (accepted, T-0494): the blue is a
snapshot. An element MOVED keeps its override (same id), an element DRAWN
after the coloring has none and therefore shows up yellow until the section is
colored again - hence the manual "color systems" action.

Nothing here opens a transaction; the caller wraps (same contract as
SectionsCreate). IronPython 2.7 - no f-strings. """

from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    Category,
    Color,
    ElementId,
    FillPatternElement,
    FilteredElementCollector,
    LinePatternElement,
    OverrideGraphicSettings,
    ParameterFilterElement,
    ParameterFilterUtilities,
    View,
)

from System.Collections.Generic import List

import RevitUtils

# Taken from SecReport (DEV extension) - do not re-invent, the two tools must
# agree: blue = existing, yellow = proposed.
HOST_COLOR = Color(0, 128, 255)
COMP_COLOR = Color(255, 255, 0)

# Host-model elements that carry the filter / the overrides. Same list as
# SecReport's builtInCategories. Insulation categories are included, so the
# host's insulation is collected directly and needs no host-element matching.
CATEGORIES = [
    BuiltInCategory.OST_CableTray,
    BuiltInCategory.OST_DuctCurves,
    BuiltInCategory.OST_DuctInsulations,
    BuiltInCategory.OST_FabricationDuctwork,
    BuiltInCategory.OST_FabricationDuctworkLining,
    BuiltInCategory.OST_FabricationDuctworkInsulation,
    BuiltInCategory.OST_PipeCurves,
    BuiltInCategory.OST_PipeInsulations,
    BuiltInCategory.OST_Conduit,
    BuiltInCategory.OST_CableTrayFitting,
    BuiltInCategory.OST_DuctFitting,
    BuiltInCategory.OST_PipeFitting,
    BuiltInCategory.OST_ConduitFitting,
    BuiltInCategory.OST_DuctTerminal,
    BuiltInCategory.OST_MechanicalEquipment,
]

FILTER_NAME = "BPM_COMP_SYSTEMS"
TEMPLATE_NAME = "BPM_Sections_Colors"

# color_template_mode values (persisted in the create settings).
MODE_NONE = "none"  # filter straight on each colored view
MODE_CREATE = "create"  # one tool-owned template carries the filter
MODE_EXISTING = "existing"  # the filter is added to a template the user picked

# Messages (shown through the window's notify).
TEMPLATE_BLOCKS_FILTER_MSG = (
    u"הצבע הצהוב לא הוחל: תבנית התצוגה '{}' של המבט שולטת בפילטרים. "
    u"בחר אותה בהגדרות תחת 'תבנית תצוגה (View Template)' - אז הצביעה תחול עליה."
)
OTHER_TEMPLATE_MSG = (
    u"הצבע הצהוב לא הוחל: על המבט מוחלת התבנית '{}' ולא '{}'. "
    u"הסר את התבנית מהמבט, או בחר אותה בהגדרות תחת 'תבנית תצוגה (View Template)'."
)
TEMPLATE_CREATE_FAILED_MSG = (
    u"לא הצלחתי ליצור את תבנית התצוגה '{}' ({}). הצהוב הוחל על המבט עצמו."
)
NO_TEMPLATE_PICKED_MSG = (
    u"הצבע הצהוב לא הוחל: לא נבחרה תבנית תצוגה בהגדרות."
)


# ----------------------------------------------------------------------
# Override graphics (copied from SecReport.getOgsByColor)
# ----------------------------------------------------------------------
def get_ogs_by_color(doc, color):
    ogs = OverrideGraphicSettings()
    ogs.SetCutBackgroundPatternColor(color)
    ogs.SetCutForegroundPatternColor(color)
    ogs.SetCutLineColor(Color(0, 0, 0))
    ogs.SetProjectionLineColor(Color(0, 0, 0))
    ogs.SetSurfaceBackgroundPatternColor(color)
    ogs.SetSurfaceForegroundPatternColor(color)

    ogs.SetSurfaceTransparency(10)

    solid_pattern_id = _solid_fill_pattern_id(doc)
    if solid_pattern_id is not None:
        ogs.SetSurfaceForegroundPatternId(solid_pattern_id)
        ogs.SetCutForegroundPatternId(solid_pattern_id)

    line_pattern = LinePatternElement.GetLinePatternElementByName(doc, "Solid")
    if line_pattern:
        ogs.SetProjectionLinePatternId(line_pattern.Id)
        ogs.SetCutLinePatternId(line_pattern.Id)

    return ogs


def _solid_fill_pattern_id(doc):
    for pattern in FilteredElementCollector(doc).OfClass(FillPatternElement):
        try:
            if pattern.GetFillPattern().IsSolidFill:
                return pattern.Id
        except Exception:
            continue
    return None


# ----------------------------------------------------------------------
# The yellow filter
# ----------------------------------------------------------------------
def _wanted_category_ids(doc):
    """The ids of CATEGORIES that exist in this model AND are filterable.

    A category missing from the model (or not filterable in this Revit
    version) would make ParameterFilterElement.Create throw and take the whole
    coloring down with it.
    """
    filterable = set(
        RevitUtils.getElementIdValue(doc, cat_id)
        for cat_id in ParameterFilterUtilities.GetAllFilterableCategories()
    )
    ids = []
    for built_in_category in CATEGORIES:
        try:
            category = Category.GetCategory(doc, built_in_category)
        except Exception:
            category = None
        if category is None:
            continue
        if RevitUtils.getElementIdValue(doc, category.Id) not in filterable:
            continue
        ids.append(category.Id)
    return ids


def find_filter(doc):
    for filter_element in FilteredElementCollector(doc).OfClass(
        ParameterFilterElement
    ):
        try:
            if filter_element.Name == FILTER_NAME:
                return filter_element
        except Exception:
            continue
    return None


def ensure_filter(doc):
    """The BPM_COMP_SYSTEMS filter, created or healed. (filter, error).

    Healing matters as much as creating (T-0494): the filter lives in the
    planner's model, where anything can happen to it between runs. Every call
    re-asserts that all the categories we color are inside it - a category the
    planner removed by hand would silently leave that discipline uncolored.
    """
    wanted = _wanted_category_ids(doc)
    if not wanted:
        return None, u"לא נמצאו קטגוריות מערכות שניתן לסנן במודל הזה."

    filter_element = find_filter(doc)
    if filter_element is None:
        try:
            return (
                ParameterFilterElement.Create(
                    doc, FILTER_NAME, List[ElementId](wanted)
                ),
                None,
            )
        except Exception as ex:
            return None, u"יצירת הפילטר '{}' נכשלה ({}).".format(FILTER_NAME, ex)

    try:
        current = list(filter_element.GetCategories())
        current_values = set(
            RevitUtils.getElementIdValue(doc, cat_id) for cat_id in current
        )
        missing = [
            cat_id
            for cat_id in wanted
            if RevitUtils.getElementIdValue(doc, cat_id) not in current_values
        ]
        if missing:
            filter_element.SetCategories(List[ElementId](current + missing))
    except Exception as ex:
        return filter_element, u"עדכון הקטגוריות של הפילטר נכשל ({}).".format(ex)

    return filter_element, None


def apply_comp_filter(doc, view):
    """Put the yellow filter on `view` (a regular view or a template). (ok, error)

    Idempotent and self-healing by design: the filter is re-added if missing,
    its visibility re-enabled, and the yellow override re-set on every call -
    so a filter whose color was changed by hand goes back to yellow.
    """
    filter_element, error = ensure_filter(doc)
    if filter_element is None:
        return False, error

    try:
        applied = set(
            RevitUtils.getElementIdValue(doc, filter_id)
            for filter_id in view.GetFilters()
        )
        if RevitUtils.getElementIdValue(doc, filter_element.Id) not in applied:
            view.AddFilter(filter_element.Id)
        view.SetFilterVisibility(filter_element.Id, True)
        view.SetFilterOverrides(
            filter_element.Id, get_ogs_by_color(doc, COMP_COLOR)
        )
    except Exception as ex:
        return False, u"החלת הפילטר על '{}' נכשלה ({}).".format(view.Name, ex)

    return True, error


# ----------------------------------------------------------------------
# The blue element overrides
# ----------------------------------------------------------------------
def colorize_host_elements(doc, view):
    """Blue-override every host-model system element visible in `view`.

    FilteredElementCollector(doc, view.Id) returns the HOST's elements only -
    a link's elements belong to the link document and are never collected.
    That is precisely what leaves them to the yellow filter.
    """
    ogs = get_ogs_by_color(doc, HOST_COLOR)
    count = 0
    for built_in_category in CATEGORIES:
        try:
            elements = (
                FilteredElementCollector(doc, view.Id)
                .OfCategory(built_in_category)
                .WhereElementIsNotElementType()
                .ToElementIds()
            )
        except Exception:
            continue
        for element_id in elements:
            try:
                view.SetElementOverrides(element_id, ogs)
                count += 1
            except Exception:
                continue
    return count


# ----------------------------------------------------------------------
# View templates
# ----------------------------------------------------------------------
def find_template_by_name(doc, name):
    for view in FilteredElementCollector(doc).OfClass(View):
        try:
            if view.IsTemplate and view.Name == name:
                return view
        except Exception:
            continue
    return None


def resolve_template(doc, template_id_int):
    """The view template with this saved id int, or None if it is gone / is no
    longer a template."""
    if template_id_int is None:
        return None
    for view in FilteredElementCollector(doc).OfClass(View):
        try:
            if not view.IsTemplate:
                continue
            if RevitUtils.getElementIdValue(doc, view.Id) == template_id_int:
                return view
        except Exception:
            continue
    return None


def _let_template_control_filters(doc, template):
    """Make sure the template actually drives the filters of its views.

    A template whose "V/G Overrides Filters" is unchecked carries the filter
    but applies it to nothing - the single way this whole mode fails silently.
    """
    try:
        target = RevitUtils.getElementIdValue(
            doc, ElementId(BuiltInParameter.VIS_GRAPHICS_FILTERS)
        )
        non_controlled = list(template.GetNonControlledTemplateParameterIds())
        remaining = [
            param_id
            for param_id in non_controlled
            if RevitUtils.getElementIdValue(doc, param_id) != target
        ]
        if len(remaining) != len(non_controlled):
            template.SetNonControlledTemplateParameterIds(
                List[ElementId](remaining)
            )
    except Exception:
        pass  # best effort - older API / unexpected template state


def ensure_color_template(doc, source_view):
    """The tool-owned BPM_Sections_Colors template, created or healed.

    (template, error). Created once from `source_view` and reused forever
    after; every call re-asserts the filter, its color and the template's
    control over filters, so a template edited by hand returns to spec.
    """
    template = find_template_by_name(doc, TEMPLATE_NAME)
    if template is None:
        if source_view is None:
            return None, TEMPLATE_CREATE_FAILED_MSG.format(
                TEMPLATE_NAME, u"אין מבט מקור"
            )
        try:
            # CreateViewTemplate returns the View itself, not an ElementId.
            template = source_view.CreateViewTemplate()
            template.Name = TEMPLATE_NAME
        except Exception as ex:
            return None, TEMPLATE_CREATE_FAILED_MSG.format(TEMPLATE_NAME, ex)

    _let_template_control_filters(doc, template)
    ok, error = apply_comp_filter(doc, template)
    if not ok:
        return None, error
    return template, error


def detach_template(view):
    """Drop the view's template. (ok, error).

    Only ever called on a FRESHLY created section: a section type can carry a
    "view template applied to new views", so a new section is born with a
    template nobody picked - and if that template controls filters, Revit
    refuses the yellow filter on the view. Detaching an existing section's
    template would be destroying a choice the planner made, so this never runs
    outside the create flow.
    """
    try:
        view.ViewTemplateId = ElementId.InvalidElementId
        return True, None
    except Exception as ex:
        return False, u"ניתוק תבנית התצוגה מהמבט '{}' נכשל ({}).".format(
            view.Name, ex
        )


def _template_of(doc, view):
    """The view's template, or None when it has none."""
    try:
        template_id = view.ViewTemplateId
        if template_id is None or template_id == ElementId.InvalidElementId:
            return None
        return doc.GetElement(template_id)
    except Exception:
        return None


def _controls_filters(doc, template):
    """True when this template drives its views' filters (so a view-level
    filter change on those views is refused by Revit)."""
    try:
        target = RevitUtils.getElementIdValue(
            doc, ElementId(BuiltInParameter.VIS_GRAPHICS_FILTERS)
        )
        for param_id in template.GetNonControlledTemplateParameterIds():
            if RevitUtils.getElementIdValue(doc, param_id) == target:
                return False
    except Exception:
        return False
    return True


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def _add_warning(report, message):
    """Keep every warning of one coloring run - a later step must not erase
    what an earlier one reported (nor overwrite it with None)."""
    if not message:
        return
    if report["warning"]:
        report["warning"] = report["warning"] + u"\n" + message
    else:
        report["warning"] = message



def colorize_section(doc, view, mode, template_id_int=None, fresh=False):
    """Color one section: blue on this model's systems, yellow on the link's.

    `mode` is one of MODE_NONE / MODE_CREATE / MODE_EXISTING (see above).
    `fresh` marks a section created seconds ago by this tool - the only case
    where dropping a template it carries is ours to decide (see
    detach_template).
    Returns {'blue': int, 'yellow': unicode or None, 'warning': unicode or
    None}. The blue half never fails on a template (element overrides are not
    template-controlled), so a yellow that could not be applied is reported as
    a warning instead of failing the whole action.

    Must run inside an open transaction on `doc`.
    """
    report = {"blue": 0, "yellow": None, "warning": None}

    # The planner picked no template, so the one the SECTION TYPE handed the
    # new view is in the way of both remaining modes - the view's own filter
    # (refused while a template controls filters) and the tool's own template.
    if fresh and mode != MODE_EXISTING:
        if _template_of(doc, view) is not None:
            ok, error = detach_template(view)
            if not ok:
                _add_warning(report, error)

    report["blue"] = colorize_host_elements(doc, view)

    if mode == MODE_CREATE:
        template, error = ensure_color_template(doc, view)
        if template is None:
            # No template to hang the filter on - fall back to the view itself
            # rather than leaving the section half colored.
            ok, view_error = apply_comp_filter(doc, view)
            report["yellow"] = view.Name if ok else None
            _add_warning(report, error or view_error)
            return report
        current = _template_of(doc, view)
        if current is None or RevitUtils.getElementIdValue(
            doc, current.Id
        ) == RevitUtils.getElementIdValue(doc, template.Id):
            try:
                view.ViewTemplateId = template.Id
            except Exception as ex:
                _add_warning(
                    report,
                    u"החלת התבנית '{}' נכשלה ({}).".format(TEMPLATE_NAME, ex),
                )
                return report
            report["yellow"] = TEMPLATE_NAME
        else:
            # Never silently replace a template the planner chose.
            _add_warning(
                report, OTHER_TEMPLATE_MSG.format(current.Name, TEMPLATE_NAME)
            )
        return report

    if mode == MODE_EXISTING:
        template = resolve_template(doc, template_id_int)
        if template is None:
            _add_warning(report, NO_TEMPLATE_PICKED_MSG)
            return report
        _let_template_control_filters(doc, template)
        ok, error = apply_comp_filter(doc, template)
        report["yellow"] = template.Name if ok else None
        _add_warning(report, error)
        return report

    # MODE_NONE - the filter goes on the view itself, which Revit refuses when
    # the view's template controls filters. On a fresh section the template was
    # already detached above, so this only bites an existing section the
    # planner templated by hand.
    template = _template_of(doc, view)
    if template is not None and _controls_filters(doc, template):
        _add_warning(report, TEMPLATE_BLOCKS_FILTER_MSG.format(template.Name))
        return report
    ok, error = apply_comp_filter(doc, view)
    report["yellow"] = view.Name if ok else None
    _add_warning(report, error)
    return report
