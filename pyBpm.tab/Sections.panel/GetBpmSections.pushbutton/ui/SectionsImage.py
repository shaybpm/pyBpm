# -*- coding: utf-8 -*-
""" Section image export + file management for Get Bpm Sections (S4).

Exports a PNG of a compilation-model section view and manages the temp files:

  - Files live in a single temp folder (%TEMP%/pyBpm_GetBpmSections) with a
    DETERMINISTIC ASCII name per (comp model, section): sec_<compguid>_<id>.png,
    so re-opening a section finds its image without re-exporting.
  - export_section_image runs on the Revit API context (ExportImage is read-only,
    no transaction). ExportRange.SetOfViews makes Revit DECORATE the output name
    ("<base> - <ViewType> - <ViewName>.png") which can't be fully controlled, so
    we export to a temp base, pick the newest matching PNG, and rename it to the
    deterministic path.
  - cull_old_files trims stale PNGs on window open so the folder never grows
    without bound; delete_files removes this session's files on window close.

IronPython 2.7. """

import os, glob, tempfile, time

FOLDER_NAME = "pyBpm_GetBpmSections"
FILE_PREFIX = "sec_"
_TEMP_BASE = "_export_tmp"
MAX_AGE_DAYS = 3


def get_folder():
    """The temp folder (created if missing)."""
    folder = os.path.join(tempfile.gettempdir(), FOLDER_NAME)
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except Exception:
            pass
    return folder


def _ascii_token(text):
    """ASCII-alnum-only token for a filename (drops hyphens etc.)."""
    return "".join(c for c in str(text) if c.isalnum())


def deterministic_path(comp_key, section_id):
    """The fixed PNG path for a (comp model key, section id) pair."""
    name = "{}{}_{}.png".format(
        FILE_PREFIX, _ascii_token(comp_key), int(section_id)
    )
    return os.path.join(get_folder(), name)


def export_section_image(comp_doc, section, dest_path):
    """Export `section` (a view in comp_doc) to dest_path as PNG. Runs on the
    Revit API context. Returns dest_path on success, None on failure."""
    from Autodesk.Revit.DB import (
        ImageExportOptions,
        ExportRange,
        ImageFileType,
        ImageResolution,
        FitDirectionType,
        ZoomFitType,
        ElementId,
    )
    from System.Collections.Generic import List

    folder = os.path.dirname(dest_path)
    base = os.path.join(folder, _TEMP_BASE)

    # Clear any stale temp exports first, then note any that survived (locked) so
    # a leftover is never mistaken for this export's fresh output.
    for old in glob.glob(base + "*"):
        try:
            os.remove(old)
        except Exception:
            pass
    leftover = set(glob.glob(base + "*"))

    options = ImageExportOptions()
    options.ExportRange = ExportRange.SetOfViews
    view_ids = List[ElementId]()
    view_ids.Add(section.Id)
    options.SetViewsAndSheets(view_ids)
    options.HLRandWFViewsFileType = ImageFileType.PNG
    options.ShadowViewsFileType = ImageFileType.PNG
    options.ImageResolution = ImageResolution.DPI_150
    options.ZoomType = ZoomFitType.FitToPage
    options.PixelSize = 1200
    options.FitDirection = FitDirectionType.Horizontal
    options.FilePath = base

    comp_doc.ExportImage(options)

    # SetOfViews decorates the name -> pick the newest PNG that Revit just wrote
    # (excluding any pre-existing locked leftover, which would be stale).
    candidates = [c for c in glob.glob(base + "*.png") if c not in leftover]
    if not candidates:
        return None
    newest = max(candidates, key=os.path.getmtime)

    try:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(newest, dest_path)
    except Exception:
        return None

    # Remove any other temp leftovers (extra views, shadow variants).
    for old in glob.glob(base + "*"):
        try:
            os.remove(old)
        except Exception:
            pass
    return dest_path


def cull_old_files(max_age_days=MAX_AGE_DAYS):
    """Delete PNGs older than max_age_days from the temp folder (best effort)."""
    folder = get_folder()
    cutoff = time.time() - max_age_days * 86400
    for path in glob.glob(os.path.join(folder, FILE_PREFIX + "*.png")):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except Exception:
            pass


def delete_files(paths):
    """Delete the given files (best effort) - used on window close."""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
