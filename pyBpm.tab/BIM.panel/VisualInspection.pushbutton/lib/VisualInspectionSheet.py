# -*- coding: utf-8 -*-
"""Put a row's mirrored views on one sheet in the planner's model.

The compilation shows a row (level x scope box) as a sheet, sometimes several
pages of it. The planner wants the same thing in their own model: every view
of that row they have mirrored, on ONE sheet, arranged, so they can look at the
storey the way the coordinator does. No title block - this is a working sheet,
not a drawing to issue, and a title block would only decide a paper size the
views then have to fit.

Only ever on an explicit click. Nothing here runs by itself.

The sheet is found again by its NAME, which is the compilation row's sheet
name: pressing the button a second time adds whatever was mirrored since onto
the same sheet instead of starting another one. A view the planner already put
on some other sheet stays there - a view lives on one sheet in Revit, and
moving it would undo their arrangement - and is reported.

IronPython 2.7. Does not open a transaction - the caller does.
"""

import math

from Autodesk.Revit.DB import (
    BuiltInParameter,
    ElementId,
    FilteredElementCollector,
    View,
    ViewSheet,
    ViewType,
    Viewport,
    XYZ,
)

import RevitUtils  # extension-level lib


# Space between viewports, in feet (1.5 cm). Small on purpose: a row's
# sections are only a few centimetres tall on paper.
GUTTER = 1.5 / 30.48

# The sheet has no paper to fill, so its width is chosen: wide enough for the
# widest view, otherwise about this aspect ratio for everything together.
TARGET_ASPECT = 1.5

# The order a row is read in: the plan, the floor from above and below, then
# the sections. The same order DEV.tab places them in on the compilation.
SLOT_ORDER = {"TOP": 0, "FLR-TOP": 1, "FLR-BOT": 2, "SEC": 3}


def row_sheet_order(item):
    """Sort key for a ViewRowItem: plans first, then sections by axis."""
    slot = item.slot or ("SEC" if item.grid_name else None)
    return (SLOT_ORDER.get(slot, 4), item.grid_name or u"", item.view_name)


def place_row(doc, number, name, views):
    """Put `views` on the row's sheet. Returns a result dict.

    `views` are the planner's own views in reading order. The result:
      sheet         - the sheet used (created or found); None when there was
                      no sheet yet and nothing to put on one
      created       - True when the sheet is new
      placed        - how many viewports were added
      elsewhere     - [(view name, sheet number)] already on another sheet
    """
    sheet = _find_sheet(doc, name)
    created = sheet is None
    if created and all(_sheet_number_of(doc, v) is not None for v in views):
        # Every view already sits on some other sheet: a new sheet would be
        # born empty and stay that way.
        return {
            "sheet": None,
            "created": False,
            "placed": 0,
            "elsewhere": [(v.Name, _sheet_number_of(doc, v)) for v in views],
        }
    if created:
        sheet = ViewSheet.Create(doc, ElementId.InvalidElementId)
        _set(sheet, BuiltInParameter.SHEET_NUMBER, _free_number(doc, number))
        _set(sheet, BuiltInParameter.SHEET_NAME, name)

    sheet_id = sheet.Id
    elsewhere = []
    viewports = []
    for view in views:
        if Viewport.CanAddViewToSheet(doc, sheet_id, view.Id):
            viewport = Viewport.Create(doc, sheet_id, view.Id, XYZ(0, 0, 0))
            viewports.append((viewport, view))
            continue
        on = _sheet_number_of(doc, view)
        if on is not None and on != sheet.SheetNumber:
            elsewhere.append((view.Name, on))

    if viewports:
        # A viewport's size on paper is its ANNOTATION crop - section heads
        # and grid bubbles reach past the model crop - so it has to exist
        # before it can be measured.
        doc.Regenerate()
        _arrange(doc, sheet, viewports)

    return {
        "sheet": sheet,
        "created": created,
        "placed": len(viewports),
        "elsewhere": elsewhere,
    }


# --- LAYOUT -------------------------------------------------------------------


def _arrange(doc, sheet, viewports):
    """Shelves, left to right and top down; plans and sections on own lines.

    Below whatever is already on the sheet, so a second press adds to the
    arrangement instead of dropping new views on top of the old ones.
    """
    items = []
    for viewport, view in viewports:
        outline = viewport.GetBoxOutline()
        low, high = outline.MinimumPoint, outline.MaximumPoint
        is_section = view.ViewType == ViewType.Section
        items.append(
            {
                "viewport": viewport,
                "width": high.X - low.X,
                "height": high.Y - low.Y,
                "group": "SEC" if is_section else "PLAN",
            }
        )

    widest = max(i["width"] for i in items)
    area = sum(i["width"] * i["height"] for i in items)
    max_width = max(widest, math.sqrt(area * TARGET_ASPECT))

    left, top = _start_corner(
        doc,
        sheet,
        set(RevitUtils.getElementIdValue(doc, i["viewport"].Id) for i in items),
    )

    cursor_x = left
    shelf_top = top
    shelf_height = 0.0
    group = None
    for item in items:
        new_group = group is not None and item["group"] != group
        too_wide = cursor_x > left and cursor_x + item["width"] > left + max_width
        if new_group or too_wide:
            shelf_top -= shelf_height + GUTTER
            cursor_x = left
            shelf_height = 0.0
        centre = XYZ(
            cursor_x + 0.5 * item["width"],
            shelf_top - 0.5 * item["height"],
            0,
        )
        item["viewport"].SetBoxCenter(centre)
        cursor_x += item["width"] + GUTTER
        shelf_height = max(shelf_height, item["height"])
        group = item["group"]


def _start_corner(doc, sheet, new_ids):
    """(left, top) for the first new viewport.

    The origin on an empty sheet; otherwise one gutter below the lowest
    viewport already there, aligned with the leftmost one.
    """
    lows = []
    lefts = []
    for viewport_id in sheet.GetAllViewports():
        viewport = doc.GetElement(viewport_id)
        if viewport is None:
            continue
        if RevitUtils.getElementIdValue(doc, viewport_id) in new_ids:
            continue
        try:
            outline = viewport.GetBoxOutline()
        except Exception:
            continue
        lows.append(outline.MinimumPoint.Y)
        lefts.append(outline.MinimumPoint.X)
    if not lows:
        return 0.0, 0.0
    return min(lefts), min(lows) - GUTTER


# --- LOOKUPS ------------------------------------------------------------------


def _find_sheet(doc, name):
    if not name:
        return None
    for sheet in FilteredElementCollector(doc).OfClass(ViewSheet).ToElements():
        try:
            if sheet.Name == name and not sheet.IsPlaceholder:
                return sheet
        except Exception:
            continue
    return None


def _free_number(doc, number):
    """The compilation's number, or the first free variant of it."""
    taken = set()
    for sheet in FilteredElementCollector(doc).OfClass(ViewSheet).ToElements():
        try:
            taken.add(sheet.SheetNumber)
        except Exception:
            continue
    base = number or u"VI"
    candidate = base
    counter = 1
    while candidate in taken:
        counter += 1
        candidate = u"{0}-{1}".format(base, counter)
    return candidate


def _sheet_number_of(doc, view):
    try:
        param = view.get_Parameter(BuiltInParameter.VIEWER_SHEET_NUMBER)
        value = param.AsString() if param is not None else None
    except Exception:
        return None
    # Revit fills it with "---" for a view on no sheet.
    if not value or value == u"---":
        return None
    return value


def _set(element, built_in, value):
    param = element.get_Parameter(built_in)
    if param is not None and not param.IsReadOnly:
        param.Set(value)


def views_by_name(doc, names):
    """{name: the planner's view} for the names that exist, one sweep."""
    wanted = set(names)
    found = {}
    for view in FilteredElementCollector(doc).OfClass(View).ToElements():
        try:
            if view.IsTemplate or isinstance(view, ViewSheet):
                continue
            if view.Name in wanted and view.Name not in found:
                found[view.Name] = view
        except Exception:
            continue
    return found
