# -*- coding: utf-8 -*-
""" Core logic for the Get Bpm Sections discipline-filter selection.

Handles the launch preconditions, collecting the compilation model's
discipline filters, persisting the planner's selection locally (per user,
scoped to both model GUIDs) and opening the selection window when needed.

Shipped as shared code under GetBpmSections.pushbutton; the main flow reuses
the saved selection, and the in-window Settings page opens the selection window.
IronPython 2.7 - no f-strings; Hebrew only inside string bodies (this is a
lib module, not a button script.py, so its strings are never parsed for
tooltips). """

import os, sys

import RevitUtils
from RevitUtils import getElementIdValue, getElementName
from LocalUserInputs import LocalUserInputs
from PyBpmAppUtils import discipline_dict

# The selection window lives in the sibling ui/ folder - make it importable.
_UI_DIR = os.path.join(os.path.dirname(__file__), "..", "ui")
if _UI_DIR not in sys.path:
    sys.path.append(_UI_DIR)

# ----------------------------- messages ---------------------------------
COMP_LINK_NOT_LOADED_MSG = "The Compilation model link is not loaded."
COMP_LINK_BROKEN_MSG = (
    "Something went wrong with the Compilation model link.\n"
    "maybe it's not loaded?"
)
NOT_IN_CLOUD_MSG = u"כלי זה זמין רק כאשר גם המודל הנוכחי וגם מודל הקומפילציה נמצאים בענן (Cloud)."
# decision #7
NO_FILTERS_MSG = u"לא נמצאו פילטרים לפי פורמט. פנה למתאם המערכות"

# Local per-user stores (persist across Revit sessions).
SELECTION_FILE = "get_bpm_sections_filter_selection"
SHEET_SCOPE_FILE = "get_bpm_sections_sheet_scope"

# Presentation order of discipline groups (values of discipline_dict).
_DISCIPLINE_ORDER = ["A", "S", "P", "SP", "C", "H", "E", "G", "F"]


def _order_key(code):
    if code in _DISCIPLINE_ORDER:
        return (_DISCIPLINE_ORDER.index(code), code)
    return (len(_DISCIPLINE_ORDER), code)


def check_preconditions(doc):
    """Validate the launch preconditions (section 4.2 of the plan).

    Returns (comp_link, comp_doc, error_message). error_message is None when
    all preconditions pass. The cloud check on ``doc`` comes first because
    ``get_comp_link`` -> ``get_model_info`` raises when the doc is not in cloud.
    """
    if not doc.IsModelInCloud:
        return None, None, NOT_IN_CLOUD_MSG

    comp_link = RevitUtils.get_comp_link(doc)
    if not comp_link:
        return None, None, COMP_LINK_NOT_LOADED_MSG

    comp_doc = comp_link.GetLinkDocument()
    if not comp_doc:
        return None, None, COMP_LINK_BROKEN_MSG

    if not comp_doc.IsModelInCloud:
        return comp_link, comp_doc, NOT_IN_CLOUD_MSG

    return comp_link, comp_doc, None


def collect_discipline_filters(comp_doc):
    """Collect the comp model's ParameterFilterElements whose name starts with a
    discipline prefix ("A - ", "SP - ", ...), grouped by discipline code.

    Returns an ordered list of {"code", "display", "filters"} dicts. Groups
    with no matching filter are omitted.
    """
    from Autodesk.Revit.DB import FilteredElementCollector, ParameterFilterElement

    all_filters = (
        FilteredElementCollector(comp_doc)
        .OfClass(ParameterFilterElement)
        .ToElements()
    )

    # discipline_dict maps display -> code, e.g. "A - Architectural" -> "A".
    code_to_display = {}
    for display, code in discipline_dict.items():
        code_to_display[code] = display

    buckets = {}
    for f in all_filters:
        name = getElementName(f)
        for code in code_to_display:
            # The " - " separator makes prefixes unambiguous (S vs SP).
            if name.startswith(code + " - "):
                buckets.setdefault(code, []).append(f)
                break

    groups = []
    for code in sorted(buckets.keys(), key=_order_key):
        flist = sorted(buckets[code], key=lambda x: getElementName(x))
        groups.append(
            {"code": code, "display": code_to_display[code], "filters": flist}
        )
    return groups


def _selection_key(doc, comp_doc):
    this_guid = RevitUtils.get_model_info(doc)["modelGuid"]
    comp_guid = RevitUtils.get_model_info(comp_doc)["modelGuid"]
    return this_guid + "__" + comp_guid


def load_saved_selection(doc, comp_doc):
    """Return the saved list of filter id ints for this (model, comp) pair, or
    None if nothing was ever saved."""
    inputs = LocalUserInputs(SELECTION_FILE)
    return inputs.data.get(_selection_key(doc, comp_doc))


def save_selection(doc, comp_doc, filter_ids):
    inputs = LocalUserInputs(SELECTION_FILE)
    inputs.data[_selection_key(doc, comp_doc)] = filter_ids
    inputs.save_inputs()


def load_sheet_scope(doc, comp_doc):
    """Return the saved list of in-scope sheet numbers for this (model, comp) pair,
    or None if never saved (caller treats None as 'all sheets')."""
    inputs = LocalUserInputs(SHEET_SCOPE_FILE)
    return inputs.data.get(_selection_key(doc, comp_doc))


def save_sheet_scope(doc, comp_doc, sheet_numbers):
    inputs = LocalUserInputs(SHEET_SCOPE_FILE)
    inputs.data[_selection_key(doc, comp_doc)] = sheet_numbers
    inputs.save_inputs()


def _filters_by_id(comp_doc, groups):
    by_id = {}
    for g in groups:
        for f in g["filters"]:
            by_id[getElementIdValue(comp_doc, f.Id)] = f
    return by_id


def _resolve_saved(comp_doc, groups, saved_ids):
    """Map saved ids back to the current discipline filters.

    Returns (valid_filters, all_present). all_present is False if any saved id
    no longer matches a current discipline filter (deleted / renamed away) -
    which forces the window to reopen (section 4.3).
    """
    by_id = _filters_by_id(comp_doc, groups)
    valid = []
    all_present = True
    for fid in saved_ids:
        if fid in by_id:
            valid.append(by_id[fid])
        else:
            all_present = False
    return valid, all_present


def ensure_filter_selection(doc, force_window=False):
    """Entry point used by the buttons.

    force_window=True (Settings) always opens the window, pre-populated with the
    current saved selection. Otherwise the window opens only when there is no
    valid saved selection (first run, or a saved id went missing).

    Returns one of:
      {"status": "ok", "filters": [...], "comp_doc": comp_doc}
      {"status": "blocked", "message": "..."}
      {"status": "cancelled"}
    """
    comp_link, comp_doc, error = check_preconditions(doc)
    if error:
        return {"status": "blocked", "message": error}

    groups = collect_discipline_filters(comp_doc)
    if not groups:
        return {"status": "blocked", "message": NO_FILTERS_MSG}

    saved_ids = load_saved_selection(doc, comp_doc)

    need_window = force_window
    preselected = []
    if not saved_ids:
        # None (never saved) or an unexpected empty list -> (re)open the window.
        need_window = True
    else:
        preselected, all_present = _resolve_saved(comp_doc, groups, saved_ids)
        if not all_present:
            need_window = True

    if not need_window:
        return {"status": "ok", "filters": preselected, "comp_doc": comp_doc}

    from FilterSelectionDialog import FilterSelectionDialog

    preselected_ids = set(getElementIdValue(comp_doc, f.Id) for f in preselected)
    dialog = FilterSelectionDialog(comp_doc, groups, preselected_ids)
    selected = dialog.show_dialog()
    if selected is None:
        return {"status": "cancelled"}

    save_selection(
        doc, comp_doc, [getElementIdValue(comp_doc, f.Id) for f in selected]
    )
    return {"status": "ok", "filters": selected, "comp_doc": comp_doc}
