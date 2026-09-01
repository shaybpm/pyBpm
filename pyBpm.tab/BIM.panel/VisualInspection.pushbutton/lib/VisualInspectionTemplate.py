# -*- coding: utf-8 -*-
"""Share the compilation view's View Template with the planner's model.

A mirrored view that is cut in the right place but drawn differently is not the
same view. The score the coordinator published was computed from an image, and
that image is what the template produced: which categories are visible, which
filters hide or recolour what. A planner looking at their own copy under their
own graphics is looking at a different drawing and will not see what scored.

So the template travels with the view:

  - not in the planner's model  ->  copied across from the compilation
  - already there by name       ->  COMPARED

Either way it ends up compared. A copy is not automatically faithful: Revit
does not copy a filter whose name already exists in the destination, it points
the new template at the model's own - so a template can arrive already behaving
differently from the one that produced the score.

A comparison that only ever reports is not worth much, so a template that
differs can be REPLACED by the compilation's - see replace_template. Nothing
here does that on its own: the template is a shared, named object and other
views in the planner's model may be on it, so the replacement is an explicit
choice made in front of a dialog that says how many views come along with it.

WHAT THE COMPARISON COVERS, and why it is mostly about filters: a filter is the
part of a template that makes elements disappear or change colour, so a filter
that differs changes what the drawing SAYS. Compared per filter: presence,
on/off visibility, the graphic overrides, and the filter's own categories and
rules. Patterns and other elements are compared by NAME, never by ElementId -
ids are meaningless across documents.

Where a rule genuinely cannot be read back through the API, the comparison says
so rather than reporting equality. An unknown reported as "same" is worse than
an unknown reported as unknown.

IronPython 2.7. No function here opens a transaction - the caller does.
"""

from Autodesk.Revit.DB import (
    CopyPasteOptions,
    DuplicateTypeAction,
    ElementId,
    ElementParameterFilter,
    ElementTransformUtils,
    FilteredElementCollector,
    IDuplicateTypeNamesHandler,
    LogicalAndFilter,
    LogicalOrFilter,
    Transform,
    View,
)
from System.Collections.Generic import List


TEMPLATE_NONE_ON_COMP = (
    u"למבט בקומפילציה לא מוחל View Template, ולכן אין מה להעתיק."
)
TEMPLATE_COPY_FAILED = u"העתקת ה-View Template מהקומפילציה נכשלה: {0}"
TEMPLATE_RENAME_FAILED = (
    u"לא ניתן היה לפנות את שם ה-View Template הקיים אצלך: {0}"
)
TEMPLATE_DELETE_FAILED = (
    u"התבנית החדשה הועתקה והמבטים הועברו אליה, אבל התבנית הישנה לא נמחקה "
    u"ונשארה במודל בשם '{0}': {1}"
)

# What the outgoing template is renamed to while its name is handed over. It
# lives under this name for a few lines only - long enough for the views to be
# moved off it - and is then deleted.
TEMPLATE_OLD_SUFFIX = u"_BPM_VI_OLD"


class _UseDestinationTypes(IDuplicateTypeNamesHandler):
    """A type name that already exists here belongs to this model, not to the
    compilation. Keeping the destination's own is the non-destructive answer.

    It also means a COPIED template is not necessarily a faithful one, which is
    why the copy is compared too - see ensure_template.
    """

    def OnDuplicateTypeNamesFound(self, args):
        return DuplicateTypeAction.UseDestinationTypes


# --- FINDING ------------------------------------------------------------------


def template_of(view):
    """The View Template applied to `view`, as an element. None when none is."""
    try:
        template_id = view.ViewTemplateId
    except Exception:
        return None
    if template_id is None or template_id == ElementId.InvalidElementId:
        return None
    try:
        return view.Document.GetElement(template_id)
    except Exception:
        return None


def find_template_by_name(doc, name):
    """A view template in `doc` with this exact name, or None."""
    if not name:
        return None
    for candidate in (
        FilteredElementCollector(doc).OfClass(View).ToElements()
    ):
        try:
            if candidate.IsTemplate and candidate.Name == name:
                return candidate
        except Exception:
            continue
    return None


# --- COPYING ------------------------------------------------------------------


def copy_template(doc, comp_doc, comp_template):
    """Copy a view template out of the compilation model. (template, error).

    The filters the template references come across with it as dependencies -
    that is the point of copying the template rather than rebuilding it.

    Must run inside an open transaction on `doc`.
    """
    if comp_template is None:
        return None, TEMPLATE_NONE_ON_COMP

    try:
        ids = List[ElementId]()
        ids.Add(comp_template.Id)

        options = CopyPasteOptions()
        options.SetDuplicateTypeNamesHandler(_UseDestinationTypes())

        copied = ElementTransformUtils.CopyElements(
            comp_doc, ids, doc, Transform.Identity, options
        )
        for new_id in copied:
            element = doc.GetElement(new_id)
            if element is not None:
                return element, None
        return None, TEMPLATE_COPY_FAILED.format(u"לא הוחזר אלמנט")
    except Exception as ex:
        return None, TEMPLATE_COPY_FAILED.format(ex)


def ensure_template(doc, comp_doc, comp_view):
    """The local twin of the comp view's template. (template, differences, error).

    Copies it when this model does not have one by that name; otherwise returns
    the model's own and the list of ways it differs. `differences` is empty when
    the two agree, and is never used to justify overwriting anything.

    Must run inside an open transaction on `doc`.
    """
    comp_template = template_of(comp_view)
    if comp_template is None:
        return None, [], TEMPLATE_NONE_ON_COMP

    try:
        name = comp_template.Name
    except Exception:
        return None, [], TEMPLATE_NONE_ON_COMP

    existing = find_template_by_name(doc, name)
    if existing is not None:
        return existing, compare_templates(comp_template, existing), None

    copied, error = copy_template(doc, comp_doc, comp_template)
    if copied is None:
        return None, [], error

    # A fresh copy is compared too, and not out of caution - it genuinely can
    # differ. Any filter whose NAME already exists in this model is not copied:
    # the duplicate-name handler keeps the model's own, and the new template
    # points at that one. Observed on a real pair of models: BONDS_MY exists in
    # both, and each carries its own user GUID in its rules, so the template
    # landed already filtering by a different person.
    return copied, compare_templates(comp_template, copied), None


def views_using(doc, template):
    """The ElementIds of every view in `doc` driven by this template.

    Ids, not views: the caller deletes the template between collecting this and
    using it, and a live handle would not survive that (see the
    revit-element-lifetime rule).
    """
    if template is None:
        return []
    template_id = template.Id
    result = []
    for view in FilteredElementCollector(doc).OfClass(View).ToElements():
        try:
            if view.IsTemplate:
                continue
            if view.ViewTemplateId == template_id:
                result.append(view.Id)
        except Exception:
            continue
    return result


def _free_template_name(doc, base):
    """A template name nothing in the model answers to."""
    candidate = base + TEMPLATE_OLD_SUFFIX
    index = 1
    while find_template_by_name(doc, candidate) is not None:
        index += 1
        candidate = u"{0}{1}{2}".format(base, TEMPLATE_OLD_SUFFIX, index)
    return candidate


def replace_template(doc, comp_doc, comp_view):
    """Make the planner's template BE the compilation's, keeping its views.

    Returns (template, moved_views, remaining, error).

    A template cannot be overwritten in place and its name cannot be taken
    while it holds it, so the swap is a four-step dance - the one Eyal
    specified: rename the local one out of the way, copy the compilation's in
    under the free name, move every view that was on the old one across, then
    delete the old one.

    Views is the word that matters. The point of the rename-first order is that
    no view is ever left pointing at nothing: they are moved onto the new
    template while the old one still exists, and only then is it deleted.

    This DOES reach past the inspection views. Any view in the planner's model
    that was on that template comes along, because the alternative - leaving
    half the model on a template that no longer exists - is worse. `moved_views`
    is how many, so the caller can say so.

    Must run inside an open transaction on `doc`; a failure part-way is the
    caller's to roll back.
    """
    comp_template = template_of(comp_view)
    if comp_template is None:
        return None, 0, [], TEMPLATE_NONE_ON_COMP

    try:
        name = comp_template.Name
    except Exception:
        return None, 0, [], TEMPLATE_NONE_ON_COMP

    existing = find_template_by_name(doc, name)
    if existing is None:
        copied, error = copy_template(doc, comp_doc, comp_template)
        if copied is None:
            return None, 0, [], error
        return copied, 0, compare_templates(comp_template, copied), None

    followers = views_using(doc, existing)
    old_id = existing.Id
    try:
        existing.Name = _free_template_name(doc, name)
    except Exception as ex:
        return None, 0, [], TEMPLATE_RENAME_FAILED.format(ex)

    copied, error = copy_template(doc, comp_doc, comp_template)
    if copied is None:
        try:
            existing.Name = name  # nothing was lost - put the name back
        except Exception:
            pass
        return None, 0, [], error

    moved = 0
    for view_id in followers:
        view = doc.GetElement(view_id)
        if view is None or not view.IsValidObject:
            continue
        try:
            view.ViewTemplateId = copied.Id
            moved += 1
        except Exception:
            continue

    try:
        doc.Delete(old_id)
    except Exception as ex:
        return copied, moved, [], TEMPLATE_DELETE_FAILED.format(name, ex)

    # Compared again, and not as a formality: this is the one comparison that
    # can still fail after a replacement, and it fails for a reason worth
    # naming - see remaining_reason().
    return copied, moved, compare_templates(comp_template, copied), None


def remaining_reason(differences):
    """Why differences can survive a replacement, in the planner's words.

    Everything the TEMPLATE itself holds - which filters it carries, whether
    each is on, its overrides, the drawing settings - is copied, so a
    replacement settles all of it. What a copy cannot settle is the definition
    of a FILTER whose name is already taken here: Revit keeps this model's own
    and points the new template at it. Replacing that would rewrite a filter
    every other view in the model shares, which is a bigger decision than this
    one and is not taken here.
    """
    if not differences:
        return None
    return (
        u"נותרו {0} הבדלים שהחלפת התבנית אינה פותרת: הם בהגדרה של פילטר "
        u"ששמו כבר תפוס אצלך, ו-Revit לא מעתיק פילטר על גבי אחד קיים — הוא "
        u"משאיר את שלך. כדי ליישר גם אותם צריך להחליף את הפילטר עצמו, וזה "
        u"משנה אותו בכל המבטים במודל שלך שמשתמשים בו."
    ).format(len(differences))


def apply_template(view, template):
    """Put the template on the view. (applied, error). Needs a transaction."""
    if template is None:
        return False, TEMPLATE_NONE_ON_COMP
    try:
        if view.ViewTemplateId == template.Id:
            return False, None
        view.ViewTemplateId = template.Id
        return True, None
    except Exception as ex:
        return False, u"לא ניתן להחיל את ה-View Template: {0}".format(ex)


# --- READ-ONLY STATUS (for the dashboard) -------------------------------------

STATE_NONE = "none"        # the comp view has no template at all
STATE_MISSING = "missing"  # not in this model yet - it would be copied
STATE_SAME = "same"        # here, and agrees with the compilation
STATE_DIFFERS = "differs"  # here, and does not


def template_status(doc, comp_view, cache=None):
    """(name, state, differences) for a comp view. Reads only, no transaction.

    `cache` is a dict the caller keeps across views. Every section of a row
    shares one template, so without it the same filter set would be compared
    once per row of the grid - the comparison walks every filter's overrides
    and rules, and that adds up.
    """
    comp_template = template_of(comp_view)
    if comp_template is None:
        return None, STATE_NONE, []

    try:
        name = comp_template.Name
    except Exception:
        return None, STATE_NONE, []

    if cache is not None and name in cache:
        return cache[name]

    existing = find_template_by_name(doc, name)
    if existing is None:
        answer = (name, STATE_MISSING, [])
    else:
        differences = compare_templates(comp_template, existing)
        answer = (
            name,
            STATE_DIFFERS if differences else STATE_SAME,
            differences,
        )

    if cache is not None:
        cache[name] = answer
    return answer


# --- COMPARING ----------------------------------------------------------------


def compare_templates(comp_template, local_template):
    """Every way the planner's template differs from the compilation's.

    A list of Hebrew one-liners, most consequential first: filters that exist
    on one side only, then filters that behave differently, then the drawing
    settings. Empty means the two agree on everything compared.
    """
    differences = []
    differences.extend(_compare_filters(comp_template, local_template))
    differences.extend(_compare_display(comp_template, local_template))
    return differences


def _filters_by_name(template):
    """{name: ParameterFilterElement} for the filters the template carries."""
    result = {}
    try:
        filter_ids = template.GetFilters()
    except Exception:
        return None  # Not readable - told apart from "no filters" by the caller.
    doc = template.Document
    for filter_id in filter_ids or []:
        try:
            element = doc.GetElement(filter_id)
            if element is not None:
                result[element.Name] = element
        except Exception:
            continue
    return result


def _compare_filters(comp_template, local_template):
    comp_filters = _filters_by_name(comp_template)
    local_filters = _filters_by_name(local_template)
    if comp_filters is None or local_filters is None:
        return [u"לא ניתן היה לקרוא את רשימת הפילטרים של אחת התבניות."]

    differences = []

    missing = sorted(set(comp_filters) - set(local_filters))
    if missing:
        differences.append(
            u"פילטרים שקיימים בקומפילציה וחסרים אצלך: {0}".format(
                u", ".join(missing)
            )
        )
    extra = sorted(set(local_filters) - set(comp_filters))
    if extra:
        differences.append(
            u"פילטרים שנוספו אצלך ואינם בקומפילציה: {0}".format(
                u", ".join(extra)
            )
        )

    for name in sorted(set(comp_filters) & set(local_filters)):
        differences.extend(
            _compare_one_filter(
                name,
                comp_template,
                local_template,
                comp_filters[name],
                local_filters[name],
            )
        )
    return differences


def _compare_one_filter(name, comp_template, local_template, comp_f, local_f):
    """How one shared filter behaves differently between the two templates."""
    differences = []

    comp_visible = _filter_visibility(comp_template, comp_f)
    local_visible = _filter_visibility(local_template, local_f)
    if comp_visible != local_visible and None not in (comp_visible, local_visible):
        differences.append(
            u"הפילטר '{0}': בקומפילציה {1}, אצלך {2}.".format(
                name,
                u"מוצג" if comp_visible else u"מוסתר",
                u"מוצג" if local_visible else u"מוסתר",
            )
        )

    comp_overrides = _overrides_signature(comp_template, comp_f)
    local_overrides = _overrides_signature(local_template, local_f)
    if comp_overrides is None or local_overrides is None:
        differences.append(
            u"הפילטר '{0}': לא ניתן היה להשוות את הגדרות הגרפיקה.".format(name)
        )
    elif comp_overrides != local_overrides:
        differences.append(
            u"הפילטר '{0}': הגדרות הגרפיקה (צבע/עובי/הצללה) שונות.".format(name)
        )

    comp_categories = _categories(comp_f)
    local_categories = _categories(local_f)
    if comp_categories != local_categories:
        differences.append(
            u"הפילטר '{0}': הקטגוריות שעליהן הוא חל שונות.".format(name)
        )

    comp_rules = _rules_signature(comp_f)
    local_rules = _rules_signature(local_f)
    if comp_rules is None or local_rules is None:
        differences.append(
            u"הפילטר '{0}': לא ניתן היה להשוות את הכללים דרך ה-API — "
            u"יש לבדוק ידנית.".format(name)
        )
    elif comp_rules != local_rules:
        differences.append(u"הפילטר '{0}': הכללים שונים.".format(name))

    return differences


def _filter_visibility(template, filter_element):
    try:
        return bool(template.GetFilterVisibility(filter_element.Id))
    except Exception:
        return None


def _overrides_signature(template, filter_element):
    """The filter's graphic overrides, as values comparable across documents.

    Patterns and line styles are ElementIds, and an id means nothing in another
    document - so every one of them is resolved to its NAME first.
    """
    try:
        overrides = template.GetFilterOverrides(filter_element.Id)
    except Exception:
        return None
    if overrides is None:
        return None

    doc = template.Document
    try:
        return (
            _color(overrides.ProjectionLineColor),
            _color(overrides.CutLineColor),
            overrides.ProjectionLineWeight,
            overrides.CutLineWeight,
            _element_name(doc, overrides.ProjectionLinePatternId),
            _element_name(doc, overrides.CutLinePatternId),
            _color(overrides.SurfaceForegroundPatternColor),
            _color(overrides.SurfaceBackgroundPatternColor),
            _color(overrides.CutForegroundPatternColor),
            _color(overrides.CutBackgroundPatternColor),
            _element_name(doc, overrides.SurfaceForegroundPatternId),
            _element_name(doc, overrides.SurfaceBackgroundPatternId),
            _element_name(doc, overrides.CutForegroundPatternId),
            _element_name(doc, overrides.CutBackgroundPatternId),
            overrides.Transparency,
            overrides.Halftone,
            overrides.IsSurfaceForegroundPatternVisible,
            overrides.IsSurfaceBackgroundPatternVisible,
            overrides.IsCutForegroundPatternVisible,
            overrides.IsCutBackgroundPatternVisible,
        )
    except Exception:
        return None


def _color(color):
    if color is None:
        return None
    try:
        if not color.IsValid:
            return None
        return (color.Red, color.Green, color.Blue)
    except Exception:
        return None


def _element_name(doc, element_id):
    """An element's name, normalised for comparing across documents.

    Case and inner whitespace are flattened. Two models routinely spell the
    same stock pattern differently - the compilation had "Dash Dot" where the
    copy landed on the destination's own "Dash dot" - and reporting that as a
    graphics difference is crying wolf about a capital letter. A genuinely
    different pattern still has a genuinely different name.
    """
    if element_id is None or element_id == ElementId.InvalidElementId:
        return None
    try:
        element = doc.GetElement(element_id)
    except Exception:
        return None
    if element is None:
        return None
    try:
        return u" ".join(u"{0}".format(element.Name).split()).lower()
    except Exception:
        return None


def _categories(filter_element):
    """The filter's categories as BuiltInCategory ints - comparable across docs."""
    try:
        return tuple(sorted(int(c.IntegerValue) for c in filter_element.GetCategories()))
    except Exception:
        try:
            return tuple(sorted(int(c) for c in filter_element.GetCategories()))
        except Exception:
            return None


def _rules_signature(filter_element):
    """A comparable summary of the filter's rules, or None when unreadable.

    None is a real answer here and is reported as "could not compare" rather
    than folded into equality - a filter whose rules changed while everything
    else stayed the same is exactly the case this is for.
    """
    try:
        element_filter = filter_element.GetElementFilter()
    except Exception:
        return None
    if element_filter is None:
        return ()

    signature = []
    if not _walk_element_filter(element_filter, filter_element.Document, signature):
        return None
    return tuple(signature)


def _walk_element_filter(element_filter, doc, signature):
    """Collect a filter tree's rules depth-first. False if anything was unreadable.

    GetRules() lives on ElementParameterFilter, and Revit almost never hands
    that back at the top: a filter built in the UI arrives as a LogicalAndFilter
    or LogicalOrFilter wrapping one or more of them (verified on 28 real office
    filters - every single one was wrapped). Calling GetRules() on the wrapper
    throws, which is why the first version reported "cannot compare" for the
    whole template.
    """
    if element_filter is None:
        return False

    if isinstance(element_filter, ElementParameterFilter):
        try:
            rules = element_filter.GetRules()
        except Exception:
            return False
        for rule in rules or []:
            entry = _rule_signature(rule, doc)
            if entry is None:
                return False
            signature.append(entry)
        return True

    if isinstance(element_filter, (LogicalAndFilter, LogicalOrFilter)):
        try:
            children = list(element_filter.GetFilters())
        except Exception:
            return False
        # The operator is part of the meaning: the same rules under AND and
        # under OR select different elements.
        signature.append((type(element_filter).__name__, len(children)))
        for child in children:
            if not _walk_element_filter(child, doc, signature):
                return False
        return True

    # Some other ElementFilter (category, class, ...). Its type is recorded so
    # two different ones do not compare equal; what it selects beyond that is
    # covered by the category comparison.
    signature.append((type(element_filter).__name__,))
    return True


def _rule_signature(rule, doc):
    """One rule as comparable values, or None when it cannot be read."""
    try:
        inner = rule.GetInnerRule()
    except Exception:
        inner = None
    if inner is not None:
        entry = _rule_signature(inner, doc)
        return None if entry is None else ("not",) + entry

    try:
        parameter_id = rule.GetRuleParameter()
    except Exception:
        return None
    # A built-in parameter has no element behind its id, and that id IS stable
    # across documents - so it can stand in for a name.
    parameter = _element_name(doc, parameter_id)
    if parameter is None:
        parameter = u"builtin:{0}".format(parameter_id)
    return (type(rule).__name__, parameter, _rule_value(rule, doc))


def _rule_value(rule, doc):
    """The value a rule tests against. None when the API does not expose it.

    A rule that tests an ElementId is resolved to that element's NAME - the id
    itself means nothing in the other document.
    """
    for attribute in ("RuleString", "RuleValue"):
        try:
            value = getattr(rule, attribute, None)
        except Exception:
            continue
        if value is None:
            continue
        if isinstance(value, ElementId):
            return _element_name(doc, value) or u"id:{0}".format(value)
        return u"{0}".format(value)
    return None


def _compare_display(comp_template, local_template):
    """The drawing settings the template controls, beyond its filters."""
    differences = []
    checks = (
        ("DetailLevel", u"רמת הפירוט (Detail Level)"),
        ("DisplayStyle", u"סגנון התצוגה (Display Style)"),
        ("Scale", u"קנה המידה"),
    )
    for attribute, label in checks:
        comp_value = _safe_attribute(comp_template, attribute)
        local_value = _safe_attribute(local_template, attribute)
        if comp_value is None or local_value is None:
            continue
        if u"{0}".format(comp_value) != u"{0}".format(local_value):
            differences.append(
                u"{0}: בקומפילציה {1}, אצלך {2}.".format(
                    label, comp_value, local_value
                )
            )
    return differences


def _safe_attribute(element, name):
    try:
        return getattr(element, name)
    except Exception:
        return None
