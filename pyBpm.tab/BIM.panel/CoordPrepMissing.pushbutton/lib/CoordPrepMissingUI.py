# -*- coding: utf-8 -*-
"""The coordination-prep missing items of the open model (BPM, T-0622): the
rows of the latest report BPM uploaded for each compilation that lists this
model, with zoom / 3D to each row's place.

Each row carries a box in the COMPILATION's internal coordinates; it reaches
this model through the compilation link's total transform, so jumping needs the
compilation loaded as a link (positioned by shared coordinates).

A modeless window: its handlers run after script.py returned, so they live in
this module, never raise (an exception in a modeless handler kills Revit), and
hold no Document - the active one is resolved on every click."""

import os
import traceback

import clr

clr.AddReference("System.Data")
# System.Windows is not importable until the WPF assemblies are referenced.
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")

from Autodesk.Revit.DB import XYZ
from System import Windows
from System.Data import DataTable
from pyrevit.framework import wpf

from ExternalEventDataFile import ExternalEventDataFile
from ReusableExternalEvents import show_bbox_3d_event
from RevitUtils import get_all_link_instances, get_model_info, get_ui_view
from ServerUtils import get_coordination_prep_reports

xaml_file = os.path.join(os.path.dirname(__file__), "CoordPrepMissingUI.xaml")

ZOOM_OFFSET_FT = 3.0
UNCERTAIN_NOTE = u"ייתכן שלא שייך למודל זה - לדיסציפלינה יש כמה מודלים."
COLUMNS = ["zone", "level", "question", "status", "status_label", "severity", "reason", "note"]
BOX_COLUMNS = ["min_x", "min_y", "min_z", "max_x", "max_y", "max_z"]

_open_windows = []  # keeps the modeless window alive after script.py returns


def _message(text, error=False):
    Windows.MessageBox.Show(
        text,
        "pyBpm",
        Windows.MessageBoxButton.OK,
        Windows.MessageBoxImage.Error if error else Windows.MessageBoxImage.Information,
    )


def _guard(fn):
    def run(self, *args):
        try:
            return fn(self, *args)
        except Exception:
            _message(u"שגיאה:\n\n{}".format(traceback.format_exc()), error=True)

    return run


def _model_guid(doc):
    try:
        return get_model_info(doc)["modelGuid"] if doc.IsModelInCloud else None
    except Exception:
        return None


def _local_time(iso_text):
    try:
        from System import DateTime
        from System.Globalization import CultureInfo, DateTimeStyles

        parsed = DateTime.Parse(iso_text, CultureInfo.InvariantCulture, DateTimeStyles.AdjustToUniversal)
        return parsed.ToLocalTime().ToString("dd/MM/yyyy HH:mm")
    except Exception:
        return (iso_text or u"")[:16].replace("T", u" ")


class CoordPrepMissingWindow(Windows.Window):
    def __init__(self, uidoc):
        wpf.LoadComponent(self, xaml_file)
        self.uiapp = uidoc.Application
        self.model_guid = _model_guid(uidoc.Document)
        self.model_name = uidoc.Document.Title
        self.reports = []
        self.report = None
        self.link_id = None  # the compilation link instance in this model
        self.Closed += lambda sender, e: _open_windows.remove(self) if self in _open_windows else None
        self.load()

    # --- data ---------------------------------------------------------------------------------

    def _doc(self):
        """The active document, if it is still the model this window is for."""
        uidoc = self.uiapp.ActiveUIDocument
        if uidoc is None or _model_guid(uidoc.Document) != self.model_guid:
            _message(u"המודל הפעיל אינו {} - יש לחזור אליו ולנסות שוב.".format(self.model_name))
            return None, None
        return uidoc, uidoc.Document

    def load(self):
        uidoc, doc = self._doc()
        if doc is None:
            return
        self.reports = get_coordination_prep_reports(doc)
        self.CompCombo.Items.Clear()
        for r in self.reports:
            self.CompCombo.Items.Add(u"{} ({})".format(r.get("compModelName") or r.get("compModelGuid"), _local_time(r.get("uploadedAt"))))
        if not self.reports:
            self.SubtitleText.Text = u"BPM עוד לא העלתה דו\"ח הכנה לתיאום שכולל את המודל הזה."
            self.RowsGrid.ItemsSource = None
            self._enable(False)
            return
        self.CompCombo.IsEnabled = len(self.reports) > 1
        self.CompCombo.SelectedIndex = 0  # fires comp_changed

    def _show_report(self, report):
        self.report = report
        rows = report.get("rows") or []
        missing = len([r for r in rows if r.get("status") == "X"])
        self.SubtitleText.Text = u"{} · דיסציפלינה: {} · עודכן {} · חסר {} · לבירור {}".format(
            self.model_name, report.get("disciplineLabel") or u"-", _local_time(report.get("uploadedAt")),
            missing, len(rows) - missing)
        table = DataTable("rows")
        for name in COLUMNS:
            table.Columns.Add(name)
        for name in BOX_COLUMNS:
            table.Columns.Add(name, clr.GetClrType(float))
        table.Columns.Add("has_box", clr.GetClrType(bool))
        for r in rows:
            row = table.NewRow()
            note = r.get("consultantNote") or u""
            if r.get("uncertain"):
                note = (UNCERTAIN_NOTE + u"\n" + note).strip()
            values = {
                "zone": r.get("zoneLabel") or u"", "level": r.get("levelLabel") or u"", "question": r.get("question") or u"",
                "status": r.get("status") or u"", "status_label": r.get("statusLabel") or u"",
                "severity": r.get("severityLabel") or u"", "reason": r.get("autoReason") or u"", "note": note,
            }
            for name, value in values.items():
                row[name] = value
            box = r.get("bbox") or {}
            row["has_box"] = bool(box.get("min") and box.get("max"))
            if row["has_box"]:
                for i, name in enumerate(BOX_COLUMNS):
                    row[name] = float((box["min"] + box["max"])[i])
            table.Rows.Add(row)
        self.RowsGrid.ItemsSource = table.DefaultView
        self._find_link()
        if not rows:
            self.StatusText.Text = u"אין חוסרים פתוחים למודל הזה בדו\"ח האחרון."

    def _find_link(self):
        """The compilation's link instance in this model, by its model GUID."""
        self.link_id = None
        uidoc, doc = self._doc()
        if doc is None:
            return
        comp_guid = self.report.get("compModelGuid")
        for link in get_all_link_instances(doc):
            link_doc = link.GetLinkDocument()
            if link_doc is not None and _model_guid(link_doc) == comp_guid:
                self.link_id = link.Id
                break
        name = self.report.get("compModelName") or comp_guid
        if self.link_id is None:
            self.LinkText.Text = u"לקפיצה למיקום יש לטעון את {} כקישור, במיקום Shared Coordinates.".format(name)
            self.LinkText.Foreground = Windows.Media.Brushes.DarkOrange
        else:
            self.LinkText.Text = u"הקומפילציה טעונה כקישור - זום ו-3D זמינים."
            self.LinkText.Foreground = Windows.Media.Brushes.SeaGreen
        self._enable(self.link_id is not None)

    def _enable(self, on):
        self.ZoomButton.IsEnabled = on
        self.BoxButton.IsEnabled = on

    def _selected_box(self):
        """(min XYZ, max XYZ) of the selected row in this model's coordinates,
        or (None, None) after telling the user why."""
        selected = self.RowsGrid.SelectedItem
        if selected is None:
            _message(u"יש לבחור שורה.")
            return None, None
        if not selected["has_box"]:
            _message(u"לשורה הזו אין מיקום בדו\"ח.")
            return None, None
        uidoc, doc = self._doc()
        if doc is None:
            return None, None
        link = doc.GetElement(self.link_id) if self.link_id is not None else None
        if link is None or not link.IsValidObject or link.GetLinkDocument() is None:
            self._find_link()
            link = doc.GetElement(self.link_id) if self.link_id is not None else None
            if link is None:
                _message(self.LinkText.Text)
                return None, None
        transform = link.GetTotalTransform()
        low = [selected[n] for n in BOX_COLUMNS[:3]]
        high = [selected[n] for n in BOX_COLUMNS[3:]]
        points = [transform.OfPoint(XYZ(x, y, z)) for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])]
        return (
            XYZ(min(p.X for p in points), min(p.Y for p in points), min(p.Z for p in points)),
            XYZ(max(p.X for p in points), max(p.Y for p in points), max(p.Z for p in points)),
        )

    # --- handlers -----------------------------------------------------------------------------

    @_guard
    def comp_changed(self, sender, e):
        index = self.CompCombo.SelectedIndex
        if 0 <= index < len(self.reports):
            self._show_report(self.reports[index])

    @_guard
    def zoom_click(self, sender, e):
        low, high = self._selected_box()
        if low is None:
            return
        uidoc, doc = self._doc()
        ui_view = get_ui_view(uidoc) if uidoc else None
        if ui_view is None:
            _message(u"לא נמצא מבט פעיל לזום.")
            return
        offset = XYZ(ZOOM_OFFSET_FT, ZOOM_OFFSET_FT, ZOOM_OFFSET_FT)
        ui_view.ZoomAndCenterRectangle(low.Subtract(offset), high.Add(offset))

    @_guard
    def box_click(self, sender, e):
        low, high = self._selected_box()
        if low is None:
            return
        uidoc, doc = self._doc()
        ExternalEventDataFile(doc).set_key_value(
            "min_max_points_dict",
            {"Min": {"X": low.X, "Y": low.Y, "Z": low.Z}, "Max": {"X": high.X, "Y": high.Y, "Z": high.Z}},
        )
        show_bbox_3d_event.Raise()

    @_guard
    def grid_double_click(self, sender, e):
        if self.RowsGrid.SelectedItem is not None and self.link_id is not None:
            self.zoom_click(sender, e)

    @_guard
    def refresh_click(self, sender, e):
        self.load()


def show(uidoc):
    if not uidoc.Document.IsModelInCloud:
        _message(u"הכפתור עובד על מודל בענן (ACC / BIM 360) בלבד.")
        return
    window = CoordPrepMissingWindow(uidoc)
    _open_windows.append(window)
    window.Show()
