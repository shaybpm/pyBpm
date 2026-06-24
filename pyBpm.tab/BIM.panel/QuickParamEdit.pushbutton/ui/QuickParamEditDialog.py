# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
# System.Data hosts DataTable/DataColumn. On .NET Framework (Revit <= 2024) it is
# "System.Data"; on .NET 8 (Revit 2025+) that assembly was split and DataTable
# now lives in "System.Data.Common". Try both so the same code loads on every
# Revit version - a failed AddReference here used to abort module import and show
# an empty pyRevit window instead of a traceback.
for _data_asm in ("System.Data", "System.Data.Common"):
    try:
        clr.AddReference(_data_asm)
    except:
        pass
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from System import String, Boolean
from System.Data import DataTable, DataColumn
from pyrevit.framework import wpf
from pyrevit import forms
import os

# NOTE: pyRevit's IronPython engine does not register System.Windows.Data /
# System.Windows.Markup as importable modules ("from ... import" fails with
# "No module named Data"), even though PresentationFramework is loaded. Reach
# Binding / XamlReader via attribute access (Windows.Data.* / Windows.Markup.*),
# the same way the rest of this file uses Windows.Controls.*.

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    ElementId,
    Transaction,
    StorageType,
    CategoryType,
)

# Version-safe element-id helpers: Revit 2026 removed ElementId.IntegerValue and
# the ElementId(int) constructor. getElementIdValue / getElementId pick the right
# API per Revit version (RevitUtils lives in the extension's lib/, on sys.path).
from RevitUtils import getElementIdValue, getElementId, getElementName

xaml_file = os.path.join(os.path.dirname(__file__), "QuickParamEditDialogUi.xaml")


# --------------------------------------------------------------------------
# ------------------------- Revit data helpers -----------------------------
# --------------------------------------------------------------------------


def get_categories_with_elements(doc):
    """Return a sorted list of {"cat_id", "name"} for every category that has
    at least one element (instance OR type) in the model, excluding the
    Invalid / Internal / AnalyticalModel category types.
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
            cid = getElementIdValue(doc, cat.Id)
            if cid in found:
                continue
            try:
                ctype = cat.CategoryType
            except:
                continue
            if ctype in (
                CategoryType.Invalid,
                CategoryType.Internal,
                CategoryType.AnalyticalModel,
            ):
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
    collector = FilteredElementCollector(doc).OfCategoryId(getElementId(doc, cat_id))
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
            # Element.Name via the proper static getter; a direct elem.Name
            # raises for many element types in IronPython (hence the Id fallback
            # the user was seeing for instances).
            nm = getElementName(type_elem) or u""
        except:
            nm = u""
        if fam and nm:
            return u"{0} : {1}".format(fam, nm)
        if nm:
            return nm
    except:
        pass
    try:
        return getElementName(elem)
    except:
        pass
    try:
        return u"Id {0}".format(getElementIdValue(elem.Document, elem.Id))
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
    """Return the parameter whose element-id value == param_id, else None."""
    for p in element.Parameters:
        try:
            if getElementIdValue(element.Document, p.Id) == param_id:
                return p
        except:
            continue
    return None


# --------------------------------------------------------------------------
# ------------------------------ WPF helpers -------------------------------
# --------------------------------------------------------------------------

def _set_grid(elem, col=None, row=None, col_span=None, row_span=None):
    if col is not None:
        Windows.Controls.Grid.SetColumn(elem, col)
    if row is not None:
        Windows.Controls.Grid.SetRow(elem, row)
    if col_span is not None:
        Windows.Controls.Grid.SetColumnSpan(elem, col_span)
    if row_span is not None:
        Windows.Controls.Grid.SetRowSpan(elem, row_span)


def _label(text, bold=False, align_center=False, wrap=False):
    lbl = Windows.Controls.Label()
    lbl.Content = text
    lbl.Padding = Windows.Thickness(6, 2, 6, 2)
    if bold:
        lbl.FontWeight = Windows.FontWeights.Bold
    if align_center:
        lbl.HorizontalContentAlignment = Windows.HorizontalAlignment.Center
    return lbl


def _row_separator():
    """A thin horizontal line placed between rows in the Categories list."""
    line = Windows.Controls.Border()
    line.Height = 1
    line.Background = Windows.Media.Brushes.LightGray
    line.Margin = Windows.Thickness(2, 0, 2, 0)
    return line


def _vertical_separator():
    """A thin vertical line used to group buttons in the Elements button bar."""
    line = Windows.Controls.Border()
    line.Width = 1
    line.Background = Windows.Media.Brushes.Gray
    line.Margin = Windows.Thickness(6, 4, 6, 4)
    return line


# Light highlight painted behind a Categories row while the mouse is over it
# (the standard Windows list-hover blue). Rows carry a Transparent background so
# the whole row - not only its child controls - is hit-testable for the hover.
_ROW_HOVER_BRUSH = Windows.Media.SolidColorBrush(
    Windows.Media.Color.FromRgb(229, 241, 251)
)


# --------------------------------------------------------------------------
# ------------------------------- Dialog -----------------------------------
# --------------------------------------------------------------------------


class QuickParamEditDialog(Windows.Window):
    def __init__(self, uidoc):
        wpf.LoadComponent(self, xaml_file)
        self.uidoc = uidoc
        self.doc = uidoc.Document

        # Elements-page state (rebuilt on every navigation into the table)
        self.columns = []           # [{param_id, name, storage_type, safe, checkbox_control, rows_with_param}]
        self.dt = None              # System.Data.DataTable bound to the DataGrid
        self._row_eids = []         # element id per DataTable row (index-aligned)
        self._col_by_pid = {}       # param_id -> column dict
        self.change_btn = None
        self.export_btn = None      # enabled only when >= 1 param column is checked
        self._datagrid = None       # the Elements DataGrid (for SelectedItems)
        self._suppress_propagate = False  # re-entrancy guard for bulk-fill
        self._cur_cat_id = None     # active category/mode (for the export file name)
        self._cur_mode = None

        # Categories-page state (search/filter box + the list it repopulates)
        self._all_categories = []
        self._cat_stack = None
        self._cat_filter_box = None

        self.show_main_page()

    # --------------------------- navigation --------------------------------

    def _set_content(self, element):
        self.MainContent.Content = element

    def _alert(self, msg, **kwargs):
        """forms.alert wrapper that re-focuses this dialog afterwards. With the
        window no longer Topmost, a modal alert can leave the dialog behind the
        Revit window, so Activate() brings it back to the front."""
        result = forms.alert(msg, **kwargs)
        self.Activate()
        return result

    # ----------------------------- page 1 ----------------------------------

    def show_main_page(self):
        page = Windows.Controls.Grid()
        r0 = Windows.Controls.RowDefinition()
        r0.Height = Windows.GridLength.Auto
        r1 = Windows.Controls.RowDefinition()
        r1.Height = Windows.GridLength.Auto
        r2 = Windows.Controls.RowDefinition()
        page.RowDefinitions.Add(r0)
        page.RowDefinitions.Add(r1)
        page.RowDefinitions.Add(r2)

        title = _label(
            "Select a category, then choose Types or Instances:", bold=True
        )
        _set_grid(title, row=0)
        page.Children.Add(title)

        # ---- filter / search row ----
        filter_grid = Windows.Controls.Grid()
        filter_grid.Margin = Windows.Thickness(6, 0, 6, 4)
        fc0 = Windows.Controls.ColumnDefinition()
        fc0.Width = Windows.GridLength.Auto
        fc1 = Windows.Controls.ColumnDefinition()
        fc1.Width = Windows.GridLength(1, Windows.GridUnitType.Star)
        filter_grid.ColumnDefinitions.Add(fc0)
        filter_grid.ColumnDefinitions.Add(fc1)

        filter_lbl = _label("Filter:")
        filter_lbl.VerticalContentAlignment = Windows.VerticalAlignment.Center
        _set_grid(filter_lbl, col=0)
        filter_grid.Children.Add(filter_lbl)

        self._cat_filter_box = Windows.Controls.TextBox()
        self._cat_filter_box.VerticalContentAlignment = (
            Windows.VerticalAlignment.Center
        )
        self._cat_filter_box.Margin = Windows.Thickness(2)
        _set_grid(self._cat_filter_box, col=1)
        filter_grid.Children.Add(self._cat_filter_box)

        _set_grid(filter_grid, row=1)
        page.Children.Add(filter_grid)

        # ---- scrollable category list ----
        scroll = Windows.Controls.ScrollViewer()
        scroll.VerticalScrollBarVisibility = (
            Windows.Controls.ScrollBarVisibility.Auto
        )
        scroll.Margin = Windows.Thickness(4)
        _set_grid(scroll, row=2)

        self._cat_stack = Windows.Controls.StackPanel()
        scroll.Content = self._cat_stack
        page.Children.Add(scroll)

        # Cache once; the filter box re-populates from this without re-querying.
        self._all_categories = get_categories_with_elements(self.doc)
        self._populate_categories(u"")
        # Wire the handler only after state is initialized (avoids early fires).
        self._cat_filter_box.TextChanged += self._on_category_filter_changed

        self._set_content(page)

    def _on_category_filter_changed(self, sender, e):
        self._populate_categories(sender.Text)

    def _populate_categories(self, filter_text):
        self._cat_stack.Children.Clear()
        if not self._all_categories:
            self._cat_stack.Children.Add(
                _label("No categories with elements were found.")
            )
            return
        ft = (filter_text or u"").strip().lower()
        matches = [
            c for c in self._all_categories if ft in (c["name"] or u"").lower()
        ]
        if not matches:
            self._cat_stack.Children.Add(_label("No matching categories."))
            return
        for i, cat in enumerate(matches):
            if i > 0:
                self._cat_stack.Children.Add(_row_separator())
            self._cat_stack.Children.Add(self._build_category_row(cat))

    def _build_category_row(self, cat):
        row = Windows.Controls.Grid()
        row.Margin = Windows.Thickness(2)
        # Transparent (not null) so the empty parts of the row receive mouse
        # events too; the handlers swap in the light hover brush on enter/leave.
        row.Background = Windows.Media.Brushes.Transparent
        row.MouseEnter += self._category_row_mouse_enter
        row.MouseLeave += self._category_row_mouse_leave
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

    def _category_row_mouse_enter(self, sender, e):
        sender.Background = _ROW_HOVER_BRUSH

    def _category_row_mouse_leave(self, sender, e):
        sender.Background = Windows.Media.Brushes.Transparent

    def _types_click(self, sender, e):
        self.show_elements_page(sender.Tag, "types")

    def _instances_click(self, sender, e):
        self.show_elements_page(sender.Tag, "instances")

    def _selected_category_label(self, cat_id, mode):
        """'<Category name> (Instances|Types)' for the chosen selection."""
        name = u""
        for c in self._all_categories:
            if c["cat_id"] == cat_id:
                name = c["name"]
                break
        mode_lbl = "Types" if mode == "types" else "Instances"
        if name:
            return u"{0}  ({1})".format(name, mode_lbl)
        return mode_lbl

    # ----------------------------- page 2 ----------------------------------

    def show_elements_page(self, cat_id, mode):
        try:
            elements = get_elements_for(self.doc, cat_id, mode)
            self._collect_table_data(elements)
        except Exception as ex:
            self._show_message_page("Failed to load elements:\n{0}".format(ex))
            return

        # Remember the active selection for the Excel export file name.
        self._cur_cat_id = cat_id
        self._cur_mode = mode
        cat_name = self._selected_category_label(cat_id, mode)

        page = Windows.Controls.Grid()
        r0 = Windows.Controls.RowDefinition()  # table
        r1 = Windows.Controls.RowDefinition()  # button bar
        r1.Height = Windows.GridLength(48)
        page.RowDefinitions.Add(r0)
        page.RowDefinitions.Add(r1)

        # DataGrid virtualizes + scrolls itself - do NOT wrap it in a ScrollViewer.
        if not self._row_eids:
            content = _label("No elements were found for this selection.")
        elif not self.columns:
            content = _label(
                "No editable parameters were found for this selection."
            )
        else:
            content = self._build_datagrid()
        _set_grid(content, row=0)
        page.Children.Add(content)

        bottom = Windows.Controls.Grid()
        bottom.Margin = Windows.Thickness(4)
        bcol0 = Windows.Controls.ColumnDefinition()
        bcol0.Width = Windows.GridLength(1, Windows.GridUnitType.Star)
        bcol1 = Windows.Controls.ColumnDefinition()
        bcol1.Width = Windows.GridLength.Auto
        bottom.ColumnDefinitions.Add(bcol0)
        bottom.ColumnDefinitions.Add(bcol1)
        _set_grid(bottom, row=1)

        # left side: the selected category (opposite the action buttons)
        cat_lbl = _label(cat_name, bold=True)
        cat_lbl.VerticalContentAlignment = Windows.VerticalAlignment.Center
        _set_grid(cat_lbl, col=0)
        bottom.Children.Add(cat_lbl)

        # right side: action buttons
        # Layout (left -> right): Export | Import  ::separator::  < Back | Change
        bar = Windows.Controls.StackPanel()
        bar.Orientation = Windows.Controls.Orientation.Horizontal
        bar.HorizontalAlignment = Windows.HorizontalAlignment.Right
        _set_grid(bar, col=1)
        bottom.Children.Add(bar)

        # Excel group (left of the separator): Import, then Export. Export
        # mirrors Change Values' enabled state - both act on the checked columns.
        import_btn = self._make_bar_button("Import Excel", self._import_excel_click)
        bar.Children.Add(import_btn)

        self.export_btn = self._make_bar_button("Export Excel", self._export_excel_click)
        self.export_btn.IsEnabled = False
        bar.Children.Add(self.export_btn)

        bar.Children.Add(_vertical_separator())

        back_btn = self._make_bar_button("< Back", self._back_to_main_click)
        bar.Children.Add(back_btn)

        self.change_btn = self._make_bar_button("Change Values", self._change_values_click)
        self.change_btn.IsEnabled = False
        bar.Children.Add(self.change_btn)

        page.Children.Add(bottom)
        self._set_content(page)

    def _make_bar_button(self, content, handler):
        btn = Windows.Controls.Button()
        btn.Content = content
        btn.Margin = Windows.Thickness(4)
        btn.Padding = Windows.Thickness(12, 4, 12, 4)
        btn.Click += handler
        return btn

    def _collect_table_data(self, elements):
        """Build self.columns (Union of editable params) and a System.Data
        DataTable (self.dt) the DataGrid binds to. Per param the table holds
        four columns keyed by a safe id: c_ (current display), n_ (new value,
        two-way editable), e_ (enabled flag) and v_ (cell visibility). Values
        live in the model so the DataGrid can virtualize/recycle cells freely;
        self._row_eids maps each table row back to its element id."""
        self.columns = []
        self._col_by_pid = {}
        self._row_eids = []

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
                    pid = getElementIdValue(self.doc, p.Id)
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

        dt = DataTable("elements")
        dt.Columns.Add(DataColumn("ElementName", clr.GetClrType(String)))
        for col in columns:
            safe = "p" + str(col["param_id"]).replace("-", "m")
            col["safe"] = safe
            col["checkbox_control"] = None
            col["rows_with_param"] = set()  # row indices that actually have it
            self._col_by_pid[col["param_id"]] = col
            dt.Columns.Add(DataColumn("c_" + safe, clr.GetClrType(String)))
            dt.Columns.Add(DataColumn("n_" + safe, clr.GetClrType(String)))
            dt.Columns.Add(DataColumn("e_" + safe, clr.GetClrType(Boolean)))
            dt.Columns.Add(
                DataColumn("v_" + safe, clr.GetClrType(Windows.Visibility))
            )
        self.columns = columns

        # Second pass: one DataRow per element.
        for elem in elements:
            try:
                eid = getElementIdValue(self.doc, elem.Id)
            except:
                continue
            row = dt.NewRow()
            row["ElementName"] = get_element_display_name(elem)
            row_index = len(self._row_eids)
            for col in columns:
                safe = col["safe"]
                param = find_param_by_id(elem, col["param_id"])
                if param is None:
                    row["c_" + safe] = u""
                    row["n_" + safe] = u""
                    row["e_" + safe] = False
                    row["v_" + safe] = Windows.Visibility.Collapsed
                    continue
                try:
                    current = read_current_value(param)
                except:
                    current = u""
                row["c_" + safe] = current
                row["n_" + safe] = current  # initial new value = current
                row["e_" + safe] = False    # disabled until the column is checked
                row["v_" + safe] = Windows.Visibility.Visible
                col["rows_with_param"].add(row_index)
            dt.Rows.Add(row)
            self._row_eids.append(eid)

        self.dt = dt

    def _build_datagrid(self):
        dg = Windows.Controls.DataGrid()
        dg.AutoGenerateColumns = False
        dg.HeadersVisibility = Windows.Controls.DataGridHeadersVisibility.Column
        # Stretch header content to the full column width so the CURRENT / NEW
        # sub-labels line up with the cell columns below. BasedOn keeps the
        # default header chrome.
        dg.ColumnHeaderStyle = Windows.Markup.XamlReader.Parse(
            '<Style '
            'xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" '
            'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" '
            'TargetType="DataGridColumnHeader" '
            'BasedOn="{StaticResource {x:Type DataGridColumnHeader}}">'
            '<Setter Property="HorizontalContentAlignment" Value="Stretch"/>'
            '</Style>'
        )
        dg.CanUserAddRows = False
        dg.CanUserDeleteRows = False
        dg.CanUserResizeRows = False
        dg.CanUserSortColumns = False
        dg.GridLinesVisibility = Windows.Controls.DataGridGridLinesVisibility.Vertical
        dg.VerticalGridLinesBrush = Windows.Media.Brushes.Black
        dg.EnableRowVirtualization = True
        dg.EnableColumnVirtualization = True

        name_col = Windows.Controls.DataGridTextColumn()
        name_col.Header = "Element"
        name_col.Binding = Windows.Data.Binding("ElementName")
        name_col.IsReadOnly = True
        name_col.MinWidth = 180
        dg.Columns.Add(name_col)

        for col in self.columns:
            tcol = Windows.Controls.DataGridTemplateColumn()
            tcol.Header = self._build_param_header(col)
            tcol.CellTemplate = self._build_cell_template(col["safe"])
            tcol.MinWidth = 200
            dg.Columns.Add(tcol)

        # FrozenColumnCount is clamped to the live column count, so set it only
        # after all columns have been added.
        dg.FrozenColumnCount = 1  # keep the element-name column pinned while scrolling
        dg.ItemsSource = self.dt.DefaultView

        self._datagrid = dg
        # Bulk-fill: when a NEW value changes in a selected row, mirror it to the
        # other selected rows (see _on_cell_value_changed). dt is already
        # populated here, so this never fires for the initial values.
        self.dt.ColumnChanged += self._on_cell_value_changed
        return dg

    def _build_param_header(self, col):
        """Live control used as a column header: checkbox + param name + the
        CURRENT|NEW sub-labels. Kept as a real control (headers are not
        virtualized) so we can hold the checkbox reference directly."""
        grid = Windows.Controls.Grid()
        grid.HorizontalAlignment = Windows.HorizontalAlignment.Stretch
        for _r in range(3):
            rd = Windows.Controls.RowDefinition()
            rd.Height = Windows.GridLength.Auto
            grid.RowDefinitions.Add(rd)

        # row 0: checkbox, centered
        checkbox = Windows.Controls.CheckBox()
        checkbox.IsChecked = False
        checkbox.Tag = col["param_id"]
        checkbox.HorizontalAlignment = Windows.HorizontalAlignment.Center
        checkbox.Margin = Windows.Thickness(0, 2, 0, 2)
        checkbox.Checked += self._header_checkbox_toggled
        checkbox.Unchecked += self._header_checkbox_toggled
        _set_grid(checkbox, row=0)
        grid.Children.Add(checkbox)
        col["checkbox_control"] = checkbox

        # row 1: parameter name, centered
        name_lbl = _label(col["name"], bold=True)
        name_lbl.HorizontalAlignment = Windows.HorizontalAlignment.Center
        _set_grid(name_lbl, row=1)
        grid.Children.Add(name_lbl)

        # row 2: CURRENT | NEW sub-labels, each left-aligned in its own half
        sub = Windows.Controls.Grid()
        sc1 = Windows.Controls.ColumnDefinition()
        sc1.Width = Windows.GridLength(1, Windows.GridUnitType.Star)
        sc2 = Windows.Controls.ColumnDefinition()
        sc2.Width = Windows.GridLength(1, Windows.GridUnitType.Star)
        sub.ColumnDefinitions.Add(sc1)
        sub.ColumnDefinitions.Add(sc2)
        cur_hdr = _label("CURRENT")
        cur_hdr.FontSize = 10
        cur_hdr.HorizontalAlignment = Windows.HorizontalAlignment.Left
        _set_grid(cur_hdr, col=0)
        sub.Children.Add(cur_hdr)
        new_hdr = _label("NEW")
        new_hdr.FontSize = 10
        new_hdr.HorizontalAlignment = Windows.HorizontalAlignment.Left
        _set_grid(new_hdr, col=1)
        sub.Children.Add(new_hdr)
        _set_grid(sub, row=2)
        grid.Children.Add(sub)
        return grid

    def _build_cell_template(self, safe):
        """DataTemplate (built per column) binding the current label, the thin
        separator and the editable NEW textbox to the row's c_/n_/e_/v_ fields."""
        xaml = (
            '<DataTemplate '
            'xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation">'
            '<Grid Visibility="{{Binding v_{s}}}">'
            '<Grid.ColumnDefinitions>'
            '<ColumnDefinition Width="*"/>'
            '<ColumnDefinition Width="1"/>'
            '<ColumnDefinition Width="*"/>'
            '</Grid.ColumnDefinitions>'
            '<TextBlock Grid.Column="0" Text="{{Binding c_{s}}}" '
            'TextAlignment="Center" VerticalAlignment="Center" Margin="4,2,4,2"/>'
            '<Border Grid.Column="1" Background="DarkGray"/>'
            '<TextBox Grid.Column="2" '
            'Text="{{Binding n_{s}, Mode=TwoWay, UpdateSourceTrigger=PropertyChanged}}" '
            'IsEnabled="{{Binding e_{s}}}" Margin="2" VerticalAlignment="Center"/>'
            '</Grid></DataTemplate>'
        ).format(s=safe)
        return Windows.Markup.XamlReader.Parse(xaml)

    def _header_checkbox_toggled(self, sender, e):
        pid = sender.Tag
        col = self._col_by_pid.get(pid)
        if col is not None:
            checked = bool(sender.IsChecked)
            en = "e_" + col["safe"]
            # Flip the enabled flag in the model; virtualized cells re-bind to it.
            for idx in col["rows_with_param"]:
                self.dt.Rows[idx][en] = checked
        self._update_change_button()

    def _on_cell_value_changed(self, sender, e):
        """Bulk-fill: if a NEW value changed in a row that is selected, copy it
        to the same parameter in every other selected row. Editing a row that is
        NOT selected simply changes that row (its own binding already did)."""
        if self._suppress_propagate:
            return
        col_name = e.Column.ColumnName
        if not col_name.startswith("n_"):
            return  # only NEW-value edits, not the c_/e_/v_ helper columns
        dg = self._datagrid
        if dg is None:
            return
        selected = [drv.Row for drv in dg.SelectedItems]
        # Only fan out when the edited row is itself selected, alongside others.
        if e.Row not in selected or len(selected) < 2:
            return
        new_val = e.ProposedValue
        self._suppress_propagate = True  # the copies below re-enter this handler
        try:
            # Mirror to the other selected rows. A selected row that lacks this
            # parameter has a hidden cell and is skipped by the transaction, so
            # setting its (unseen) value is harmless.
            for r in selected:
                if r is not e.Row:
                    r[col_name] = new_val
        finally:
            self._suppress_propagate = False

    def _checked_columns(self):
        """The param columns whose header checkbox is currently checked."""
        result = []
        for col in self.columns:
            cb = col["checkbox_control"]
            if cb is not None and cb.IsChecked:
                result.append(col)
        return result

    def _update_change_button(self):
        # Change Values and Export Excel both operate on the checked columns, so
        # both are enabled only while at least one parameter column is checked.
        any_checked = len(self._checked_columns()) > 0
        if self.change_btn is not None:
            self.change_btn.IsEnabled = any_checked
        if self.export_btn is not None:
            self.export_btn.IsEnabled = any_checked

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

        t = Transaction(self.doc, "pyBpm | Quick Param Edit")
        t.Start()
        try:
            for col in self.columns:
                cb = col["checkbox_control"]
                if cb is None or not cb.IsChecked:
                    continue
                pid = col["param_id"]
                cname = "c_" + col["safe"]
                nname = "n_" + col["safe"]
                for idx in col["rows_with_param"]:
                    row = self.dt.Rows[idx]
                    cur_val = row[cname]
                    new_val = row[nname]
                    cur_val = u"" if cur_val is None else unicode(cur_val)
                    new_val = u"" if new_val is None else unicode(new_val)
                    if new_val == cur_val:
                        continue  # only changed cells
                    eid = self._row_eids[idx]
                    element = self.doc.GetElement(getElementId(self.doc, eid))
                    if element is None:
                        continue
                    param = find_param_by_id(element, pid)
                    if param is None:
                        continue
                    attempted += 1
                    ename = row["ElementName"]
                    try:
                        ok = set_param_value(param, new_val)
                        if ok:
                            success += 1
                        else:
                            errors.append(
                                (eid, ename, col["name"], u"Set returned False")
                            )
                    except Exception as ex:
                        errors.append((eid, ename, col["name"], unicode(ex)))
            t.Commit()
        except Exception as ex:
            if t.HasStarted() and not t.HasEnded():
                t.RollBack()
            errors.append((0, u"", u"", u"Transaction failed: {0}".format(ex)))

        return success, attempted, errors

    # --------------------------- Excel I/O ---------------------------------
    # Pure-Python only (works on .NET 8 / Revit 2026): xlsxwriter to write,
    # xlrd to read - both bundled with pyRevit. NEVER the COM ExcelUtils here.

    def _cell(self, row, col_name):
        """A DataTable cell as a clean unicode string (DBNull/None -> u'')."""
        v = row[col_name]
        return u"" if v is None else unicode(v)

    def _safe_filename(self, text):
        out = []
        for ch in (text or u""):
            out.append(ch if (ch.isalnum() or ch in (u"-", u"_")) else u"_")
        return u"".join(out).strip(u"_") or u"export"

    # ------- export -------

    def _export_excel_click(self, sender, e):
        cols = self._checked_columns()
        if not cols:
            return  # the button is disabled in this state; guard anyway
        folder = forms.pick_folder(title="Select a folder to save the Excel file")
        if not folder:
            return
        try:
            from ExcelUtilsPure import xlsxwriter  # bundled, pure-Python

            path = self._build_export_path(folder)
            self._write_excel(path, cols, xlsxwriter)
        except Exception as ex:
            self._alert(
                u"Failed to export Excel:\n{0}".format(ex),
                title="Quick Param Edit",
            )
            return
        if self._alert(
            u"Excel exported to:\n{0}\n\nOpen it now?".format(path),
            title="Quick Param Edit",
            yes=True,
            no=True,
        ):
            try:
                os.startfile(path)
            except Exception as ex:
                self._alert(
                    u"Could not open the file:\n{0}".format(ex),
                    title="Quick Param Edit",
                )

    def _build_export_path(self, folder):
        from System import DateTime

        stamp = DateTime.Now.ToString("yyyyMMdd_HHmm")
        label = self._safe_filename(
            self._selected_category_label(self._cur_cat_id, self._cur_mode)
        )
        return os.path.join(
            folder, u"QuickParamEdit_{0}_{1}.xlsx".format(label, stamp)
        )

    def _write_excel(self, path, cols, xlsxwriter):
        """Layout: col 0 IDS / col 1 Names (each merged over the 3 header rows);
        then a 2-column block per checked parameter - row0 param.Id, row1 name
        (both merged across the block), row2 CURRENT | NEW. Data from row 3."""
        wb = xlsxwriter.Workbook(path)
        ws = wb.add_worksheet("Quick Param Edit")
        # Header (all 3 rows): dark-blue fill, white bold text.
        hdr = wb.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "bg_color": "#305496",
                "font_color": "#FFFFFF",
            }
        )
        # IDS / Names identity columns: light-blue fill, dark-blue text.
        ident = wb.add_format(
            {"border": 1, "bg_color": "#D9E1F2", "font_color": "#1F3864"}
        )
        # CURRENT columns: gray fill + gray text - signals "read-only, not for edit".
        current_fmt = wb.add_format(
            {"border": 1, "bg_color": "#D9D9D9", "font_color": "#808080"}
        )
        # NEW columns: plain white - this is what the user edits.
        new_fmt = wb.add_format({"border": 1})

        ws.merge_range(0, 0, 2, 0, "IDS", hdr)
        ws.merge_range(0, 1, 2, 1, "Names", hdr)
        c = 2
        for col in cols:
            ws.merge_range(0, c, 0, c + 1, col["param_id"], hdr)
            ws.merge_range(1, c, 1, c + 1, col["name"], hdr)
            ws.write_string(2, c, "CURRENT", hdr)
            ws.write_string(2, c + 1, "NEW", hdr)
            c += 2

        r = 3
        for idx in range(len(self._row_eids)):
            row = self.dt.Rows[idx]
            ws.write_number(r, 0, self._row_eids[idx], ident)
            ws.write_string(r, 1, self._cell(row, "ElementName"), ident)
            c = 2
            for col in cols:
                if idx in col["rows_with_param"]:
                    ws.write_string(r, c, self._cell(row, "c_" + col["safe"]), current_fmt)
                    ws.write_string(r, c + 1, self._cell(row, "n_" + col["safe"]), new_fmt)
                else:
                    ws.write_blank(r, c, None, current_fmt)
                    ws.write_blank(r, c + 1, None, new_fmt)
                c += 2
            r += 1

        ws.set_column(0, 0, 12)
        ws.set_column(1, 1, 30)
        if cols:
            ws.set_column(2, 1 + 2 * len(cols), 18)
        ws.freeze_panes(3, 2)
        wb.close()

    # ------- import -------

    def _import_excel_click(self, sender, e):
        path = forms.pick_excel_file(title="Select the edited Excel file")
        if not path:
            return
        try:
            import xlrd  # bundled, pure-Python; reads .xlsx (xlrd 1.x)

            updated, skipped = self._read_excel(path, xlrd)
        except Exception as ex:
            self._alert(
                u"Failed to import Excel:\n{0}".format(ex),
                title="Quick Param Edit",
            )
            return
        msg = u"Imported {0} value(s) into the table.".format(updated)
        if skipped:
            msg += u"\n{0} cell(s) skipped (parameter not in the table).".format(
                skipped
            )
        self._alert(msg, title="Quick Param Edit")

    def _read_excel(self, path, xlrd):
        book = xlrd.open_workbook(path)
        sheet = book.sheet_by_index(0)
        if sheet.nrows < 4 or sheet.ncols < 4:
            return 0, 0

        # Each 2-col block: param.Id sits in the merged top-left header cell
        # (left col of the block); locate the NEW sub-column via the row-2 label.
        new_col_to_pid = {}
        c = 2
        while c + 1 < sheet.ncols:
            pid = self._as_int(sheet.cell_value(0, c))
            label_left = unicode(sheet.cell_value(2, c)).strip().upper()
            new_col = c if label_left == u"NEW" else c + 1
            if pid is not None:
                new_col_to_pid[new_col] = pid
            c += 2

        eid_to_idx = {}
        for i, eid in enumerate(self._row_eids):
            eid_to_idx[eid] = i

        updated = 0
        skipped = 0
        self._suppress_propagate = True  # don't trigger bulk-fill on these writes
        try:
            for r in range(3, sheet.nrows):
                eid = self._as_int(sheet.cell_value(r, 0))
                if eid is None or eid not in eid_to_idx:
                    continue  # row for a different selection - ignore silently
                idx = eid_to_idx[eid]
                for new_col, pid in new_col_to_pid.items():
                    col = self._col_by_pid.get(pid)
                    if col is None or idx not in col["rows_with_param"]:
                        skipped += 1
                        continue
                    val = self._clean_num_str(
                        unicode(sheet.cell_value(r, new_col))
                    )
                    self.dt.Rows[idx]["n_" + col["safe"]] = val
                    updated += 1
        finally:
            self._suppress_propagate = False

        # Auto-check every imported parameter so Change Values will apply it.
        # Setting IsChecked fires _header_checkbox_toggled (sets e_ flags +
        # refreshes the Change/Export buttons).
        for pid in set(new_col_to_pid.values()):
            col = self._col_by_pid.get(pid)
            if col is not None and col["checkbox_control"] is not None:
                col["checkbox_control"].IsChecked = True

        return updated, skipped

    def _as_int(self, v):
        try:
            if v is None or v == u"" or v == "":
                return None
            return int(round(float(v)))
        except (ValueError, TypeError):
            return None

    def _clean_num_str(self, s):
        """xlrd returns numeric cells as floats, so a user-typed 3000 reads back
        as '3000.0'. Trim a trailing '.0' on otherwise-integer strings."""
        if s.endswith(u".0"):
            head = s[:-2]
            if head.lstrip(u"-").isdigit():
                return head
        return s

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
