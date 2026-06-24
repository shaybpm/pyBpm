# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from pyrevit.framework import wpf
import os

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    ElementId,
    Transaction,
    StorageType,
    CategoryType,
)

xaml_file = os.path.join(os.path.dirname(__file__), "QuickParamEditDialogUi.xaml")


# --------------------------------------------------------------------------
# ------------------------- Revit data helpers -----------------------------
# --------------------------------------------------------------------------


def get_categories_with_elements(doc):
    """Return a sorted list of {"cat_id", "name"} for every Model/Annotation
    category that has at least one element (instance OR type) in the model.
    Fully generic: nothing about the categories is hardcoded."""
    found = {}
    collectors = [
        FilteredElementCollector(doc).WhereElementIsNotElementType(),
        FilteredElementCollector(doc).WhereElementIsElementType(),
    ]
    for collector in collectors:
        for elem in collector:
            try:
                cat = elem.Category
            except:
                cat = None
            if cat is None:
                continue
            cid = cat.Id.IntegerValue
            if cid in found:
                continue
            try:
                ctype = cat.CategoryType
            except:
                continue
            if ctype != CategoryType.Model and ctype != CategoryType.Annotation:
                continue
            name = cat.Name
            if not name:
                continue
            found[cid] = name

    result = [{"cat_id": cid, "name": found[cid]} for cid in found]
    result.sort(key=lambda c: (c["name"] or u"").lower())
    return result


def get_elements_for(doc, cat_id, mode):
    """mode == 'types' -> element types ; mode == 'instances' -> instances."""
    collector = FilteredElementCollector(doc).OfCategoryId(ElementId(cat_id))
    if mode == "types":
        collector = collector.WhereElementIsElementType()
    else:
        collector = collector.WhereElementIsNotElementType()
    return list(collector.ToElements())


def get_element_display_name(elem):
    """Best-effort 'Family : Type' (or Name) display string. Never raises."""
    try:
        type_elem = elem
        if hasattr(elem, "GetTypeId"):
            tid = elem.GetTypeId()
            if tid is not None and tid != ElementId.InvalidElementId:
                te = elem.Document.GetElement(tid)
                if te is not None:
                    type_elem = te
        fam = u""
        try:
            fam = type_elem.FamilyName or u""
        except:
            fam = u""
        nm = u""
        try:
            nm = type_elem.Name or u""
        except:
            nm = u""
        if fam and nm:
            return u"{0} : {1}".format(fam, nm)
        if nm:
            return nm
    except:
        pass
    try:
        return elem.Name
    except:
        pass
    try:
        return u"Id {0}".format(elem.Id.IntegerValue)
    except:
        return u"<unknown>"


def read_current_value(param):
    """Read the current value as a display string, per StorageType."""
    st = param.StorageType
    if st == StorageType.String:
        v = param.AsString()
        return v if v is not None else u""
    if st == StorageType.Double:
        v = param.AsValueString()
        return v if v is not None else u""
    if st == StorageType.Integer:
        v = param.AsValueString()
        if v is not None:
            return v
        return unicode(param.AsInteger())
    return u""


def set_param_value(param, text):
    """Write a display-string value back to the parameter, per StorageType.
    Returns a bool: True on success, False on a value that could not be applied
    (the caller reports failures; it never relies on an exception for a bad value).
    """
    st = param.StorageType
    if st == StorageType.String:
        return param.Set(text)
    if st == StorageType.Double:
        return param.SetValueString(text)
    if st == StorageType.Integer:
        # SetValueString honors project display units / numeric Yes-No ("1"/"0").
        if param.SetValueString(text):
            return True
        # Fallback: Yes/No params are shown as "Yes"/"No" by AsValueString, but
        # SetValueString rejects those words -> map them, then plain integers.
        token = (text or u"").strip().lower()
        if token in (u"yes", u"true", u"y"):
            return param.Set(1)
        if token in (u"no", u"false", u"n"):
            return param.Set(0)
        try:
            return param.Set(int(token))
        except (ValueError, TypeError):
            return False  # unparseable -> reported as a failed cell, never crashes
    return False


def find_param_by_id(element, param_id):
    """Return the parameter whose Id.IntegerValue == param_id, else None."""
    for p in element.Parameters:
        try:
            if p.Id.IntegerValue == param_id:
                return p
        except:
            continue
    return None


# --------------------------------------------------------------------------
# ------------------------------ WPF helpers -------------------------------
# --------------------------------------------------------------------------

THICK = 3.0
THIN = 1.0


def _set_grid(elem, col=None, row=None, col_span=None, row_span=None):
    if col is not None:
        Windows.Controls.Grid.SetColumn(elem, col)
    if row is not None:
        Windows.Controls.Grid.SetRow(elem, row)
    if col_span is not None:
        Windows.Controls.Grid.SetColumnSpan(elem, col_span)
    if row_span is not None:
        Windows.Controls.Grid.SetRowSpan(elem, row_span)


def _separator(col, total_rows, thick):
    b = Windows.Controls.Border()
    b.Background = (
        Windows.Media.Brushes.Black if thick else Windows.Media.Brushes.DarkGray
    )
    _set_grid(b, col=col, row=0, row_span=total_rows)
    return b


def _label(text, bold=False, align_center=False, wrap=False):
    lbl = Windows.Controls.Label()
    lbl.Content = text
    lbl.Padding = Windows.Thickness(6, 2, 6, 2)
    if bold:
        lbl.FontWeight = Windows.FontWeights.Bold
    if align_center:
        lbl.HorizontalContentAlignment = Windows.HorizontalAlignment.Center
    return lbl


# --------------------------------------------------------------------------
# ------------------------------- Dialog -----------------------------------
# --------------------------------------------------------------------------


class QuickParamEditDialog(Windows.Window):
    def __init__(self, uidoc):
        wpf.LoadComponent(self, xaml_file)
        self.uidoc = uidoc
        self.doc = uidoc.Document

        # Elements-page state (rebuilt on every navigation into the table)
        self.columns = []           # [{param_id, name, storage_type, checkbox_control, textboxes}]
        self.rows = []              # [{element_id, name}]
        self.cells = {}             # (element_id, param_id) -> {textbox_control, current_value_str}
        self._col_by_pid = {}       # param_id -> column dict
        self.change_btn = None

        self.show_main_page()

    # --------------------------- navigation --------------------------------

    def _set_content(self, element):
        self.MainContent.Content = element

    # ----------------------------- page 1 ----------------------------------

    def show_main_page(self):
        page = Windows.Controls.Grid()
        r0 = Windows.Controls.RowDefinition()
        r0.Height = Windows.GridLength.Auto
        r1 = Windows.Controls.RowDefinition()
        page.RowDefinitions.Add(r0)
        page.RowDefinitions.Add(r1)

        title = _label(
            "Select a category, then choose Types or Instances:", bold=True
        )
        _set_grid(title, row=0)
        page.Children.Add(title)

        scroll = Windows.Controls.ScrollViewer()
        scroll.VerticalScrollBarVisibility = (
            Windows.Controls.ScrollBarVisibility.Auto
        )
        scroll.Margin = Windows.Thickness(4)
        _set_grid(scroll, row=1)

        stack = Windows.Controls.StackPanel()
        scroll.Content = stack

        categories = get_categories_with_elements(self.doc)
        if not categories:
            stack.Children.Add(_label("No categories with elements were found."))
        else:
            for cat in categories:
                stack.Children.Add(self._build_category_row(cat))

        page.Children.Add(scroll)
        self._set_content(page)

    def _build_category_row(self, cat):
        row = Windows.Controls.Grid()
        row.Margin = Windows.Thickness(2)
        c0 = Windows.Controls.ColumnDefinition()
        c0.Width = Windows.GridLength(1, Windows.GridUnitType.Star)
        c1 = Windows.Controls.ColumnDefinition()
        c1.Width = Windows.GridLength.Auto
        c2 = Windows.Controls.ColumnDefinition()
        c2.Width = Windows.GridLength.Auto
        row.ColumnDefinitions.Add(c0)
        row.ColumnDefinitions.Add(c1)
        row.ColumnDefinitions.Add(c2)

        name_lbl = _label(cat["name"])
        name_lbl.VerticalContentAlignment = Windows.VerticalAlignment.Center
        _set_grid(name_lbl, col=0)
        row.Children.Add(name_lbl)

        types_btn = Windows.Controls.Button()
        types_btn.Content = "Types"
        types_btn.Tag = cat["cat_id"]
        types_btn.Margin = Windows.Thickness(2)
        types_btn.Padding = Windows.Thickness(10, 2, 10, 2)
        types_btn.Click += self._types_click
        _set_grid(types_btn, col=1)
        row.Children.Add(types_btn)

        inst_btn = Windows.Controls.Button()
        inst_btn.Content = "Instances"
        inst_btn.Tag = cat["cat_id"]
        inst_btn.Margin = Windows.Thickness(2)
        inst_btn.Padding = Windows.Thickness(10, 2, 10, 2)
        inst_btn.Click += self._instances_click
        _set_grid(inst_btn, col=2)
        row.Children.Add(inst_btn)

        return row

    def _types_click(self, sender, e):
        self.show_elements_page(sender.Tag, "types")

    def _instances_click(self, sender, e):
        self.show_elements_page(sender.Tag, "instances")

    # ----------------------------- page 2 ----------------------------------

    def show_elements_page(self, cat_id, mode):
        try:
            elements = get_elements_for(self.doc, cat_id, mode)
            self._collect_table_data(elements)
        except Exception as ex:
            self._show_message_page("Failed to load elements:\n{0}".format(ex))
            return

        page = Windows.Controls.Grid()
        r0 = Windows.Controls.RowDefinition()  # table
        r1 = Windows.Controls.RowDefinition()  # button bar
        r1.Height = Windows.GridLength(48)
        page.RowDefinitions.Add(r0)
        page.RowDefinitions.Add(r1)

        scroll = Windows.Controls.ScrollViewer()
        scroll.HorizontalScrollBarVisibility = (
            Windows.Controls.ScrollBarVisibility.Auto
        )
        scroll.VerticalScrollBarVisibility = (
            Windows.Controls.ScrollBarVisibility.Auto
        )
        scroll.Content = self._build_table()
        _set_grid(scroll, row=0)
        page.Children.Add(scroll)

        bar = Windows.Controls.StackPanel()
        bar.Orientation = Windows.Controls.Orientation.Horizontal
        bar.HorizontalAlignment = Windows.HorizontalAlignment.Right
        bar.Margin = Windows.Thickness(4)
        _set_grid(bar, row=1)

        back_btn = Windows.Controls.Button()
        back_btn.Content = "< Back"
        back_btn.Margin = Windows.Thickness(4)
        back_btn.Padding = Windows.Thickness(12, 4, 12, 4)
        back_btn.Click += self._back_to_main_click
        bar.Children.Add(back_btn)

        self.change_btn = Windows.Controls.Button()
        self.change_btn.Content = "Change Values"
        self.change_btn.Margin = Windows.Thickness(4)
        self.change_btn.Padding = Windows.Thickness(12, 4, 12, 4)
        self.change_btn.IsEnabled = False
        self.change_btn.Click += self._change_values_click
        bar.Children.Add(self.change_btn)

        page.Children.Add(bar)
        self._set_content(page)

    def _collect_table_data(self, elements):
        """Build self.columns (Union of editable params), self.rows and the
        per-cell current-value strings. Controls are created in _build_table."""
        self.columns = []
        self.rows = []
        self.cells = {}
        self._col_by_pid = {}

        columns_map = {}  # param_id -> {param_id, name, storage_type}
        editable = (StorageType.String, StorageType.Integer, StorageType.Double)

        # First pass: discover the union of editable parameters.
        for elem in elements:
            try:
                params = elem.Parameters
            except:
                continue
            for p in params:
                try:
                    if p.IsReadOnly:
                        continue
                    st = p.StorageType
                    if st not in editable:
                        continue
                    pid = p.Id.IntegerValue
                    if pid not in columns_map:
                        columns_map[pid] = {
                            "param_id": pid,
                            "name": p.Definition.Name,
                            "storage_type": st,
                        }
                except:
                    continue

        columns = list(columns_map.values())
        columns.sort(key=lambda c: (c["name"] or u"").lower())
        for col in columns:
            col["checkbox_control"] = None
            col["textboxes"] = []
            self._col_by_pid[col["param_id"]] = col
        self.columns = columns

        # Second pass: rows + current values per cell.
        for elem in elements:
            try:
                eid = elem.Id.IntegerValue
            except:
                continue
            self.rows.append(
                {"element_id": eid, "name": get_element_display_name(elem)}
            )
            for col in self.columns:
                param = find_param_by_id(elem, col["param_id"])
                if param is None:
                    continue
                try:
                    current = read_current_value(param)
                except:
                    current = u""
                self.cells[(eid, col["param_id"])] = {
                    "textbox_control": None,
                    "current_value_str": current,
                }

    def _build_table(self):
        grid = Windows.Controls.Grid()
        grid.Margin = Windows.Thickness(2)

        n_params = len(self.columns)
        total_rows = 3 + len(self.rows)

        if n_params == 0:
            return _label("No editable parameters were found for this selection.")

        # ---- columns: [names][thick] then per param [cur][thin][new][thick] ----
        name_col = Windows.Controls.ColumnDefinition()
        name_col.Width = Windows.GridLength.Auto
        name_col.MinWidth = 180
        grid.ColumnDefinitions.Add(name_col)  # 0

        thick0 = Windows.Controls.ColumnDefinition()
        thick0.Width = Windows.GridLength(THICK)
        grid.ColumnDefinitions.Add(thick0)  # 1

        for _i in range(n_params):
            cur = Windows.Controls.ColumnDefinition()
            cur.Width = Windows.GridLength.Auto
            cur.MinWidth = 110
            grid.ColumnDefinitions.Add(cur)
            thin = Windows.Controls.ColumnDefinition()
            thin.Width = Windows.GridLength(THIN)
            grid.ColumnDefinitions.Add(thin)
            new = Windows.Controls.ColumnDefinition()
            new.Width = Windows.GridLength.Auto
            new.MinWidth = 110
            grid.ColumnDefinitions.Add(new)
            thick = Windows.Controls.ColumnDefinition()
            thick.Width = Windows.GridLength(THICK)
            grid.ColumnDefinitions.Add(thick)

        for _r in range(total_rows):
            rd = Windows.Controls.RowDefinition()
            rd.Height = Windows.GridLength.Auto
            grid.RowDefinitions.Add(rd)

        # ---- element-names header (spans the 3 header rows) ----
        names_header = _label("Element", bold=True)
        names_header.VerticalContentAlignment = Windows.VerticalAlignment.Bottom
        _set_grid(names_header, col=0, row=0, row_span=3)
        grid.Children.Add(names_header)

        # ---- thick separator after the names column ----
        grid.Children.Add(_separator(1, total_rows, True))

        # ---- per-parameter headers + separators ----
        for i, col in enumerate(self.columns):
            base = 2 + i * 4
            cur_col = base
            new_col = base + 2
            thin_col = base + 1
            thick_col = base + 3

            checkbox = Windows.Controls.CheckBox()
            checkbox.IsChecked = False
            checkbox.Tag = col["param_id"]
            checkbox.HorizontalAlignment = Windows.HorizontalAlignment.Center
            checkbox.Margin = Windows.Thickness(0, 4, 0, 2)
            checkbox.Checked += self._checkbox_toggled
            checkbox.Unchecked += self._checkbox_toggled
            _set_grid(checkbox, col=cur_col, row=0, col_span=3)
            grid.Children.Add(checkbox)
            col["checkbox_control"] = checkbox

            name_lbl = _label(col["name"], bold=True, align_center=True)
            name_lbl.HorizontalAlignment = Windows.HorizontalAlignment.Center
            _set_grid(name_lbl, col=cur_col, row=1, col_span=3)
            grid.Children.Add(name_lbl)

            cur_hdr = _label("CURRENT VALUE", bold=True, align_center=True)
            cur_hdr.FontSize = 10
            _set_grid(cur_hdr, col=cur_col, row=2)
            grid.Children.Add(cur_hdr)

            new_hdr = _label("NEW VALUE", bold=True, align_center=True)
            new_hdr.FontSize = 10
            _set_grid(new_hdr, col=new_col, row=2)
            grid.Children.Add(new_hdr)

            grid.Children.Add(_separator(thin_col, total_rows, False))
            grid.Children.Add(_separator(thick_col, total_rows, True))

        # ---- value rows ----
        for r_index, row in enumerate(self.rows):
            grid_row = 3 + r_index
            eid = row["element_id"]

            name_lbl = _label(row["name"])
            name_lbl.ToolTip = u"ElementId: {0}".format(eid)
            _set_grid(name_lbl, col=0, row=grid_row)
            grid.Children.Add(name_lbl)

            for i, col in enumerate(self.columns):
                base = 2 + i * 4
                cur_col = base
                new_col = base + 2
                cell = self.cells.get((eid, col["param_id"]))
                if cell is None:
                    continue

                cur_lbl = _label(cell["current_value_str"])
                cur_lbl.FontSize = 11
                _set_grid(cur_lbl, col=cur_col, row=grid_row)
                grid.Children.Add(cur_lbl)

                textbox = Windows.Controls.TextBox()
                textbox.Text = cell["current_value_str"]
                textbox.IsEnabled = False
                textbox.Margin = Windows.Thickness(2)
                textbox.MinWidth = 100
                _set_grid(textbox, col=new_col, row=grid_row)
                grid.Children.Add(textbox)

                cell["textbox_control"] = textbox
                col["textboxes"].append(textbox)

        return grid

    def _checkbox_toggled(self, sender, e):
        pid = sender.Tag
        col = self._col_by_pid.get(pid)
        if col is not None:
            enabled = bool(sender.IsChecked)
            for tb in col["textboxes"]:
                tb.IsEnabled = enabled
        self._update_change_button()

    def _update_change_button(self):
        if self.change_btn is None:
            return
        any_checked = False
        for col in self.columns:
            cb = col["checkbox_control"]
            if cb is not None and cb.IsChecked:
                any_checked = True
                break
        self.change_btn.IsEnabled = any_checked

    def _back_to_main_click(self, sender, e):
        self.show_main_page()

    # ------------------------- transaction ---------------------------------

    def _change_values_click(self, sender, e):
        success, attempted, errors = self._apply_changes()
        self.show_summary_page(success, attempted, errors)

    def _apply_changes(self):
        success = 0
        attempted = 0
        errors = []  # (element_id, element_name, param_name, message)

        # Map element_id -> name for error reporting.
        name_by_eid = {}
        for row in self.rows:
            name_by_eid[row["element_id"]] = row["name"]

        t = Transaction(self.doc, "pyBpm | Quick Param Edit")
        t.Start()
        try:
            for col in self.columns:
                cb = col["checkbox_control"]
                if cb is None or not cb.IsChecked:
                    continue
                pid = col["param_id"]
                for row in self.rows:
                    eid = row["element_id"]
                    cell = self.cells.get((eid, pid))
                    if cell is None:
                        continue
                    new_val = cell["textbox_control"].Text
                    if new_val == cell["current_value_str"]:
                        continue  # only changed cells
                    element = self.doc.GetElement(ElementId(eid))
                    if element is None:
                        continue
                    param = find_param_by_id(element, pid)
                    if param is None:
                        continue
                    attempted += 1
                    try:
                        ok = set_param_value(param, new_val)
                        if ok:
                            success += 1
                        else:
                            errors.append(
                                (eid, name_by_eid.get(eid, u""), col["name"],
                                 u"Set returned False")
                            )
                    except Exception as ex:
                        errors.append(
                            (eid, name_by_eid.get(eid, u""), col["name"], unicode(ex))
                        )
            t.Commit()
        except Exception as ex:
            if t.HasStarted() and not t.HasEnded():
                t.RollBack()
            errors.append((0, u"", u"", u"Transaction failed: {0}".format(ex)))

        return success, attempted, errors

    # ----------------------------- page 3 ----------------------------------

    def show_summary_page(self, success, attempted, errors):
        page = Windows.Controls.Grid()
        r0 = Windows.Controls.RowDefinition()
        r0.Height = Windows.GridLength.Auto
        r1 = Windows.Controls.RowDefinition()
        r2 = Windows.Controls.RowDefinition()
        r2.Height = Windows.GridLength(48)
        page.RowDefinitions.Add(r0)
        page.RowDefinitions.Add(r1)
        page.RowDefinitions.Add(r2)

        title = _label(
            "Updated {0} of {1} values.".format(success, attempted), bold=True
        )
        title.FontSize = 14
        _set_grid(title, row=0)
        page.Children.Add(title)

        scroll = Windows.Controls.ScrollViewer()
        scroll.VerticalScrollBarVisibility = (
            Windows.Controls.ScrollBarVisibility.Auto
        )
        scroll.Margin = Windows.Thickness(4)
        _set_grid(scroll, row=1)

        stack = Windows.Controls.StackPanel()
        scroll.Content = stack

        if not errors:
            ok_lbl = _label("All changes were applied successfully.")
            stack.Children.Add(ok_lbl)
        else:
            stack.Children.Add(
                _label("{0} change(s) failed:".format(len(errors)), bold=True)
            )
            for (eid, ename, pname, msg) in errors:
                line = Windows.Controls.TextBlock()
                line.TextWrapping = Windows.TextWrapping.Wrap
                line.Margin = Windows.Thickness(6, 2, 6, 2)
                if eid:
                    line.Text = u"• {0} (Id {1}) — [{2}]: {3}".format(
                        ename, eid, pname, msg
                    )
                else:
                    line.Text = u"• {0}".format(msg)
                stack.Children.Add(line)

        page.Children.Add(scroll)

        bar = Windows.Controls.StackPanel()
        bar.Orientation = Windows.Controls.Orientation.Horizontal
        bar.HorizontalAlignment = Windows.HorizontalAlignment.Right
        bar.Margin = Windows.Thickness(4)
        _set_grid(bar, row=2)

        back_btn = Windows.Controls.Button()
        back_btn.Content = "Back to categories"
        back_btn.Margin = Windows.Thickness(4)
        back_btn.Padding = Windows.Thickness(12, 4, 12, 4)
        back_btn.Click += self._back_to_main_click
        bar.Children.Add(back_btn)

        close_btn = Windows.Controls.Button()
        close_btn.Content = "Close"
        close_btn.Margin = Windows.Thickness(4)
        close_btn.Padding = Windows.Thickness(12, 4, 12, 4)
        close_btn.Click += self._close_click
        bar.Children.Add(close_btn)

        page.Children.Add(bar)
        self._set_content(page)

    def _close_click(self, sender, e):
        self.Close()

    # ----------------------------- shared ----------------------------------

    def _show_message_page(self, message):
        page = Windows.Controls.Grid()
        r0 = Windows.Controls.RowDefinition()
        r1 = Windows.Controls.RowDefinition()
        r1.Height = Windows.GridLength(48)
        page.RowDefinitions.Add(r0)
        page.RowDefinitions.Add(r1)

        msg = Windows.Controls.TextBlock()
        msg.Text = message
        msg.TextWrapping = Windows.TextWrapping.Wrap
        msg.Margin = Windows.Thickness(10)
        _set_grid(msg, row=0)
        page.Children.Add(msg)

        back_btn = Windows.Controls.Button()
        back_btn.Content = "< Back"
        back_btn.HorizontalAlignment = Windows.HorizontalAlignment.Right
        back_btn.Margin = Windows.Thickness(4)
        back_btn.Padding = Windows.Thickness(12, 4, 12, 4)
        back_btn.Click += self._back_to_main_click
        _set_grid(back_btn, row=1)
        page.Children.Add(back_btn)

        self._set_content(page)
