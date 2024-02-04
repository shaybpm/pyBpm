# -*- coding: utf-8 -*-

import clr

clr.AddReferenceByPartialName("System")
clr.AddReference("System.Windows.Forms")
clr.AddReference("IronPython.Wpf")

from Autodesk.Revit.DB import XYZ, BoundingBoxXYZ

from System import DateTime, TimeZoneInfo
import wpf
from System import Windows
import os

from pyrevit import forms

from ServerUtils import get_openings_changes  # type: ignore
from RevitUtils import convertRevitNumToCm, get_ui_view as ru_get_ui_doc, get_transform_by_model_guid  # type: ignore

xaml_file = os.path.join(os.path.dirname(__file__), "TrackingOpeningsDialogUi.xaml")


def get_utc_offset_str():
    time_now = DateTime.Now
    utc_offset_number = int(TimeZoneInfo.Local.GetUtcOffset(time_now).TotalHours)
    if utc_offset_number > 0:
        utc_offset_num_digits = len(str(utc_offset_number))
        if utc_offset_num_digits == 1:
            return "+0{}:00".format(utc_offset_number)
        elif utc_offset_num_digits == 2:
            return "+{}:00".format(utc_offset_number)
    elif utc_offset_number < 0:
        utc_offset_num_digits = len(str(utc_offset_number))
        if utc_offset_num_digits == 2:
            return "-0{}:00".format(abs(utc_offset_number))
        elif utc_offset_num_digits == 3:
            return "-{}:00".format(abs(utc_offset_number))
    else:
        return "Z"


def get_center(bbox, axis):
    if axis == "x":
        return (bbox["max"]["x"] + bbox["min"]["x"]) / 2
    elif axis == "y":
        return (bbox["max"]["y"] + bbox["min"]["y"]) / 2
    elif axis == "z":
        return (bbox["max"]["z"] + bbox["min"]["z"]) / 2


def get_location_changes(doc, opening):
    if opening["currentBBox"] is None or opening["lastBBox"] is None:
        return "", "", ""

    x_current_center = get_center(opening["currentBBox"], "x")
    y_current_center = get_center(opening["currentBBox"], "y")
    z_current_center = get_center(opening["currentBBox"], "z")

    x_last_center = get_center(opening["lastBBox"], "x")
    y_last_center = get_center(opening["lastBBox"], "y")
    z_last_center = get_center(opening["lastBBox"], "z")

    return (
        str(round(convertRevitNumToCm(doc, x_current_center - x_last_center), 2))
        + " cm",
        str(round(convertRevitNumToCm(doc, y_current_center - y_last_center), 2))
        + " cm",
        str(round(convertRevitNumToCm(doc, z_current_center - z_last_center), 2))
        + " cm",
    )


class TrackingOpeningsDialog(Windows.Window):
    def __init__(self, uidoc):
        wpf.LoadComponent(self, xaml_file)

        self.uidoc = uidoc
        self.doc = self.uidoc.Document

        self._openings = []
        self._display_openings = []
        self._current_selected_opening = []

        self.start_time_str = None
        self.end_time_str = None

        time_now = DateTime.Now
        self.end_date_DatePicker.SelectedDate = time_now
        time_yesterday = time_now.AddDays(-1)
        self.start_date_DatePicker.SelectedDate = time_yesterday

        self.time_string_format = "yyyy-MM-ddTHH:mm:00.000Z".replace(
            "Z", get_utc_offset_str()
        )
        time_now_str = time_now.ToString(self.time_string_format)

        time_yesterday_str = time_yesterday.ToString(self.time_string_format)
        self.start_time_str = time_yesterday_str

        self.add_minutes_to_Combobox(self.start_minute_ComboBox)
        self.start_minute_ComboBox.SelectedValue = self.get_minute_by_time_string(
            time_yesterday_str
        )
        self.add_minutes_to_Combobox(self.end_minute_ComboBox)
        self.end_minute_ComboBox.SelectedValue = self.get_minute_by_time_string(
            time_now_str
        )
        self.add_hours_to_Combobox(self.start_hour_ComboBox)
        self.start_hour_ComboBox.SelectedValue = self.get_hour_by_time_string(
            time_yesterday_str
        )
        self.add_hours_to_Combobox(self.end_hour_ComboBox)
        self.end_hour_ComboBox.SelectedValue = self.get_hour_by_time_string(
            time_now_str
        )

        self.start_date_DatePicker.SelectedDateChanged += self.update_start_date_event
        self.start_hour_ComboBox.SelectionChanged += self.update_start_date_event
        self.start_minute_ComboBox.SelectionChanged += self.update_start_date_event

        self.end_date_DatePicker.SelectedDateChanged += self.update_end_date_event
        self.end_hour_ComboBox.SelectionChanged += self.update_end_date_event
        self.end_minute_ComboBox.SelectionChanged += self.update_end_date_event

        self.update_start_date()
        self.update_end_date()

        self._current_sort_key = None
        self.data_table_col_sizes = [64, 60, 80, 120]
        self.data_table_col_sizes.append(384 - sum(self.data_table_col_sizes))
        (
            self.sort_discipline_btn,
            self.sort_mark_btn,
            self.sort_changeType_btn,
            self.sort_scheduleLevel_btn,
            self.sort_floor_btn,
        ) = self.init_title_data_grid()

        self.data_listbox.SelectionChanged += self.data_listbox_selection_changed

        self.ALL_LEVELS = "All Levels"
        self.ALL_SHAPES = "All Shapes"
        self.ALL_DISCIPLINES = "All Disciplines"
        self.FLOORS_AND_WALLS = "Floors and Walls"
        self.set_all_filters()
        self.level_filter_ComboBox.SelectionChanged += (
            self.level_filter_ComboBox_SelectionChanged
        )
        self.shape_filter_ComboBox.SelectionChanged += (
            self.shape_filter_ComboBox_SelectionChanged
        )
        self.discipline_filter_ComboBox.SelectionChanged += (
            self.discipline_filter_ComboBox_SelectionChanged
        )
        self.floor_filter_ComboBox.SelectionChanged += (
            self.floor_filter_ComboBox_SelectionChanged
        )

    @property
    def display_openings(self):
        return self._display_openings

    @display_openings.setter
    def display_openings(self, value):
        self._display_openings = value
        list_box = self.data_listbox
        list_box.Items.Clear()
        for opening in self._display_openings:
            list_box.Items.Add(ListBoxItemOpening(opening, self.data_table_col_sizes))
        self.number_of_displayed_data_TextBlock.Text = str(len(self._display_openings))

    @property
    def openings(self):
        return self._openings

    @openings.setter
    def openings(self, value):
        self._openings = value
        self.display_openings = value
        self.number_of_data_TextBlock.Text = str(len(self._openings))
        self.set_all_filters()

    @property
    def current_selected_opening(self):
        return self._current_selected_opening

    @current_selected_opening.setter
    def current_selected_opening(self, value):
        self._current_selected_opening = value
        self.update_more_data_info()

    @property
    def current_sort_key(self):
        return self._current_sort_key

    @current_sort_key.setter
    def current_sort_key(self, value):
        try:
            self._current_sort_key = value
            self.sort_discipline_btn.Background = Windows.Media.Brushes.White
            self.sort_mark_btn.Background = Windows.Media.Brushes.White
            self.sort_changeType_btn.Background = Windows.Media.Brushes.White
            self.sort_scheduleLevel_btn.Background = Windows.Media.Brushes.White
            self.sort_floor_btn.Background = Windows.Media.Brushes.White
            if value is None:
                return
            if value == "discipline":
                self.sort_discipline_btn.Background = Windows.Media.Brushes.LightBlue
                return
            if value == "mark":
                self.sort_mark_btn.Background = Windows.Media.Brushes.LightBlue
                return
            if value == "changeType":
                self.sort_changeType_btn.Background = Windows.Media.Brushes.LightBlue
                return
            if value == "currentScheduledLevel":
                self.sort_scheduleLevel_btn.Background = Windows.Media.Brushes.LightBlue
                return
            if value == "isFloorOpening":
                self.sort_floor_btn.Background = Windows.Media.Brushes.LightBlue
                return
        except Exception as ex:
            print(ex)

    def alert(self, message):
        forms.alert(message, title="מעקב פתחים")
        self.Topmost = True

    def set_all_filters(self):
        self.level_filter_ComboBox.Items.Clear()
        self.level_filter_ComboBox.Items.Add(self.ALL_LEVELS)
        self.level_filter_ComboBox.SelectedIndex = 0
        current_scheduled_levels = [x["currentScheduledLevel"] for x in self.openings]
        last_scheduled_levels = [x["lastScheduledLevel"] for x in self.openings]
        all_scheduled_levels = list(
            set(current_scheduled_levels + last_scheduled_levels)
        )
        all_scheduled_levels = sorted(all_scheduled_levels)
        for level in all_scheduled_levels:
            if level is None:
                continue
            self.level_filter_ComboBox.Items.Add(level)

        self.shape_filter_ComboBox.Items.Clear()
        self.shape_filter_ComboBox.Items.Add(self.ALL_SHAPES)
        self.shape_filter_ComboBox.SelectedIndex = 0
        current_shapes = [x["currentShape"] for x in self.openings]
        last_shapes = [x["lastShape"] for x in self.openings]
        all_shapes = list(set(current_shapes + last_shapes))
        all_shapes = sorted(all_shapes)
        for shape in all_shapes:
            if shape is None:
                continue
            self.shape_filter_ComboBox.Items.Add(shape)

        self.discipline_filter_ComboBox.Items.Clear()
        self.discipline_filter_ComboBox.Items.Add(self.ALL_DISCIPLINES)
        self.discipline_filter_ComboBox.SelectedIndex = 0
        disciplines = [x["discipline"] for x in self.openings]
        all_disciplines = list(set(disciplines))
        all_disciplines = sorted(all_disciplines)
        for discipline in all_disciplines:
            if discipline is None:
                continue
            self.discipline_filter_ComboBox.Items.Add(discipline)

        self.floor_filter_ComboBox.Items.Clear()
        self.floor_filter_ComboBox.Items.Add(self.FLOORS_AND_WALLS)
        self.floor_filter_ComboBox.SelectedIndex = 0
        self.floor_filter_ComboBox.Items.Add("Floors")
        self.floor_filter_ComboBox.Items.Add("Walls")

    def level_filter_ComboBox_SelectionChanged(self, sender, e):
        self.filter_openings()

    def shape_filter_ComboBox_SelectionChanged(self, sender, e):
        self.filter_openings()

    def discipline_filter_ComboBox_SelectionChanged(self, sender, e):
        self.filter_openings()

    def floor_filter_ComboBox_SelectionChanged(self, sender, e):
        self.filter_openings()

    def filter_openings(self):
        self.display_openings = self.openings
        if self.level_filter_ComboBox.SelectedIndex != 0:
            selected_level = self.level_filter_ComboBox.SelectedValue
            self.display_openings = [
                x
                for x in self.display_openings
                if x["currentScheduledLevel"] == selected_level
                # or x["lastScheduledLevel"] == selected_level
            ]
        if self.shape_filter_ComboBox.SelectedIndex != 0:
            selected_shape = self.shape_filter_ComboBox.SelectedValue
            self.display_openings = [
                x
                for x in self.display_openings
                if x["currentShape"] == selected_shape
                # or x["lastShape"] == selected_shape
            ]
        if self.discipline_filter_ComboBox.SelectedIndex != 0:
            selected_discipline = self.discipline_filter_ComboBox.SelectedValue
            self.display_openings = [
                x
                for x in self.display_openings
                if x["discipline"] == selected_discipline
            ]
        if self.floor_filter_ComboBox.SelectedIndex != 0:
            selected_floor = self.floor_filter_ComboBox.SelectedValue
            if selected_floor == "Floors":
                self.display_openings = [
                    x for x in self.display_openings if x["isFloorOpening"]
                ]
            elif selected_floor == "Walls":
                self.display_openings = [
                    x for x in self.display_openings if not x["isFloorOpening"]
                ]

    def data_listbox_selection_changed(self, sender, e):
        list_box = sender
        selected_items = [item.opening for item in list_box.SelectedItems]
        self.current_selected_opening = selected_items

    def clear_more_data_info(self):
        self.more_info_internalDocId_TextBlock.Text = ""
        self.more_info_isNotThereMoreUpdatedStates_TextBlock.Text = ""
        self.more_info_isNotThereMoreUpdatedStates_TextBlock.Background = (
            Windows.Media.Brushes.Transparent
        )
        self.more_info_isFloorOpening_TextBlock.Text = ""
        self.more_info_currentScheduledLevel_TextBlock.Text = ""
        self.more_info_currentShape_TextBlock.Text = ""
        self.more_info_currentMct_TextBlock.Text = ""
        self.more_info_lastScheduledLevel_TextBlock.Text = ""
        self.more_info_lastShape_TextBlock.Text = ""
        self.more_info_lastMct_TextBlock.Text = ""
        self.x_location_changes_TextBlock.Text = ""
        self.y_location_changes_TextBlock.Text = ""
        self.z_location_changes_TextBlock.Text = ""

    def update_more_data_info(self):
        if len(self.current_selected_opening) != 1:
            self.clear_more_data_info()
            return
        opening = self.current_selected_opening[0]
        self.more_info_internalDocId_TextBlock.Text = str(opening["internalDocId"])
        self.more_info_isNotThereMoreUpdatedStates_TextBlock.Text = (
            "Yes" if not opening["isThereMoreUpdatedStates"] else "No"
        )
        self.more_info_isNotThereMoreUpdatedStates_TextBlock.Background = (
            Windows.Media.Brushes.LightPink
            if opening["isThereMoreUpdatedStates"]
            else Windows.Media.Brushes.Transparent
        )
        self.more_info_isFloorOpening_TextBlock.Text = (
            "Yes" if opening["isFloorOpening"] else "No"
        )

        get_short_shape = lambda shape: "○" if shape == "circular" else "◻"

        self.more_info_currentScheduledLevel_TextBlock.Text = (
            opening["currentScheduledLevel"] if opening["currentScheduledLevel"] else ""
        )
        self.more_info_currentShape_TextBlock.Text = (
            get_short_shape(opening["currentShape"]) if opening["currentShape"] else ""
        )
        self.more_info_currentMct_TextBlock.Text = (
            "Yes" if opening["currentMct"] else "No"
        )
        self.more_info_lastScheduledLevel_TextBlock.Text = (
            opening["lastScheduledLevel"] if opening["lastScheduledLevel"] else ""
        )
        self.more_info_lastShape_TextBlock.Text = (
            get_short_shape(opening["lastShape"]) if opening["lastShape"] else ""
        )
        self.more_info_lastMct_TextBlock.Text = "Yes" if opening["lastMct"] else "No"
        (
            self.x_location_changes_TextBlock.Text,
            self.y_location_changes_TextBlock.Text,
            self.z_location_changes_TextBlock.Text,
        ) = get_location_changes(self.doc, opening)

    def get_date_by_time_string(self, time_str):
        if time_str is None:
            return None
        return DateTime.Parse(time_str)

    def get_hour_by_time_string(self, time_str):
        if time_str is None:
            return None
        return time_str[11:13]

    def get_minute_by_time_string(self, time_str):
        if time_str is None:
            return None
        return time_str[14:16]

    def init_title_data_grid(self):
        grid = self.title_data_grid
        for size in self.data_table_col_sizes:
            grid_column = Windows.Controls.ColumnDefinition()
            grid.ColumnDefinitions.Add(grid_column)
            grid_column.Width = Windows.GridLength(size)

        sort_discipline_btn = Windows.Controls.Button()
        sort_discipline_btn.Content = "Discipline"
        sort_discipline_btn.Click += self.sort_discipline_btn_click
        sort_discipline_btn.Background = Windows.Media.Brushes.White
        grid.Children.Add(sort_discipline_btn)
        Windows.Controls.Grid.SetColumn(sort_discipline_btn, 0)

        sort_mark_btn = Windows.Controls.Button()
        sort_mark_btn.Content = "Mark"
        sort_mark_btn.Click += self.sort_mark_btn_click
        sort_mark_btn.Background = Windows.Media.Brushes.White
        grid.Children.Add(sort_mark_btn)
        Windows.Controls.Grid.SetColumn(sort_mark_btn, 1)

        sort_changeType_btn = Windows.Controls.Button()
        sort_changeType_btn.Content = "Change Type"
        sort_changeType_btn.Click += self.sort_changeType_btn_click
        sort_changeType_btn.Background = Windows.Media.Brushes.White
        grid.Children.Add(sort_changeType_btn)
        Windows.Controls.Grid.SetColumn(sort_changeType_btn, 2)

        sort_scheduleLevel_btn = Windows.Controls.Button()
        sort_scheduleLevel_btn.Content = "Level"
        sort_scheduleLevel_btn.Click += self.sort_scheduleLevel_btn_click
        sort_scheduleLevel_btn.Background = Windows.Media.Brushes.White
        grid.Children.Add(sort_scheduleLevel_btn)
        Windows.Controls.Grid.SetColumn(sort_scheduleLevel_btn, 3)

        sort_floor_btn = Windows.Controls.Button()
        sort_floor_btn.Content = "Floor"
        sort_floor_btn.Click += self.sort_floor_btn_click
        sort_floor_btn.Background = Windows.Media.Brushes.White
        grid.Children.Add(sort_floor_btn)
        Windows.Controls.Grid.SetColumn(sort_floor_btn, 4)

        return (
            sort_discipline_btn,
            sort_mark_btn,
            sort_changeType_btn,
            sort_scheduleLevel_btn,
            sort_floor_btn,
        )

    def sort_data_by(self, key):
        self.display_openings = sorted(
            self.display_openings,
            key=lambda k: (
                int(k[key]) if type(k[key]) is str and k[key].isdigit() else k[key]
            ),
            reverse=self.current_sort_key == key,
        )
        if self.current_sort_key == key:
            self.current_sort_key = None
        else:
            self.current_sort_key = key

    def sort_discipline_btn_click(self, sender, e):
        self.sort_data_by("discipline")

    def sort_mark_btn_click(self, sender, e):
        self.sort_data_by("mark")

    def sort_changeType_btn_click(self, sender, e):
        self.sort_data_by("changeType")

    def sort_scheduleLevel_btn_click(self, sender, e):
        self.sort_data_by("currentScheduledLevel")

    def sort_floor_btn_click(self, sender, e):
        self.sort_data_by("isFloorOpening")

    def add_nums_to_Combobox(self, combobox, start, end):
        for i in range(start, end):
            i_str = str(i)
            if len(i_str) == 1:
                i_str = "0" + i_str
            combobox.Items.Add(i_str)

    def add_minutes_to_Combobox(self, combobox):
        self.add_nums_to_Combobox(combobox, 0, 60)

    def add_hours_to_Combobox(self, combobox):
        self.add_nums_to_Combobox(combobox, 0, 24)

    def get_time_str(self, date, hour, minute):
        if date is None or hour is None or minute is None:
            return None
        return "{}T{}:{}:00.000Z".format(
            date.ToString("yyyy-MM-dd"), hour, minute
        ).replace("Z", get_utc_offset_str())

    def is_time_validate(self):
        if self.end_date_DatePicker.SelectedDate is None:
            return False
        if self.start_date_DatePicker.SelectedDate is None:
            return False
        if (
            self.start_date_DatePicker.SelectedDate.Date
            > self.end_date_DatePicker.SelectedDate.Date
        ):
            return False
        if (
            self.start_date_DatePicker.SelectedDate.Date
            == self.end_date_DatePicker.SelectedDate.Date
            and int(self.start_hour_ComboBox.SelectedValue)
            > int(self.end_hour_ComboBox.SelectedValue)
        ):
            return False
        if (
            self.start_date_DatePicker.SelectedDate.Date
            == self.end_date_DatePicker.SelectedDate.Date
            and int(self.start_hour_ComboBox.SelectedValue)
            == int(self.end_hour_ComboBox.SelectedValue)
            and int(self.start_minute_ComboBox.SelectedValue)
            >= int(self.end_minute_ComboBox.SelectedValue)
        ):
            return False
        return True

    def handle_show_openings_btn_enabled(self):
        if self.is_time_validate():
            self.show_openings_btn.IsEnabled = True
        else:
            self.show_openings_btn.IsEnabled = False

    def update_start_date(self):
        if not self.start_date_DatePicker.SelectedDate:
            return
        self.start_time_str = self.get_time_str(
            self.start_date_DatePicker.SelectedDate.Date,
            self.start_hour_ComboBox.SelectedValue,
            self.start_minute_ComboBox.SelectedValue,
        )
        self.handle_show_openings_btn_enabled()

    def update_start_date_event(self, sender, e):
        self.update_start_date()

    def update_end_date(self):
        if not self.end_date_DatePicker.SelectedDate:
            return
        self.end_time_str = self.get_time_str(
            self.end_date_DatePicker.SelectedDate.Date,
            self.end_hour_ComboBox.SelectedValue,
            self.end_minute_ComboBox.SelectedValue,
        )
        self.handle_show_openings_btn_enabled()

    def update_end_date_event(self, sender, e):
        self.update_end_date()

    def get_dates_by_latest_sheet_versions_btn_click(self, sender, e):
        pass

    def show_openings_btn_click(self, sender, e):
        try:
            self.openings = get_openings_changes(
                self.doc, self.start_time_str, self.end_time_str
            )
            format_display = "dd.MM.yyyy, HH:mm"
            start_time_display_str = DateTime.Parse(self.start_time_str).ToString(
                format_display
            )
            end_time_display_str = DateTime.Parse(self.end_time_str).ToString(
                format_display
            )
            self.current_start_date_TextBlock.Text = start_time_display_str
            self.current_end_date_TextBlock.Text = end_time_display_str
        except Exception as ex:
            print(ex)

    def get_current_selected_opening(self):
        if len(self.current_selected_opening) != 1:
            self.alert("יש לבחור פתח אחד בלבד")
            return
        return self.current_selected_opening[0]

    def get_bbox(self, opening, current=True):
        transform = get_transform_by_model_guid(self.doc, opening["modelGuid"])
        if not transform:
            self.alert("לא נמצא הלינק של הפתח הנבחר")
            return

        bbox_key_name = "currentBBox" if current else "lastBBox"
        if bbox_key_name not in opening or opening[bbox_key_name] is None:
            msg = "לא נמצא מיקום הפתח הנבחר.\n{}".format(
                'מפני שזהו אלמנט חדש, עליך ללחוץ על "הצג פתח".'
                if not current
                else 'מפני שזהו אלמנט שנמחק, עליך ללחוץ על "הצג מיקום קודם".'
            )
            self.alert(msg)
            return
        db_bbox = opening[bbox_key_name]

        bbox = BoundingBoxXYZ()
        bbox.Min = transform.OfPoint(
            XYZ(db_bbox["min"]["x"], db_bbox["min"]["y"], db_bbox["min"]["z"])
        )
        bbox.Max = transform.OfPoint(
            XYZ(db_bbox["max"]["x"], db_bbox["max"]["y"], db_bbox["max"]["z"])
        )

        return bbox

    def get_ui_view(self):
        ui_view = ru_get_ui_doc(self.uidoc)
        if not ui_view:
            self.alert("לא נמצא תצוגה פעילה")
            return
        return ui_view

    def show_opening(self, current):
        opening = self.get_current_selected_opening()
        if not opening:
            return

        bbox = self.get_bbox(opening, current)
        if not bbox:
            return

        ui_view = self.get_ui_view()
        if not ui_view:
            return

        zoom_increment = 0.08
        zoom_viewCorner1 = bbox.Min.Add(
            XYZ(-zoom_increment, -zoom_increment, -zoom_increment)
        )
        zoom_viewCorner2 = bbox.Max.Add(
            XYZ(zoom_increment, zoom_increment, zoom_increment)
        )
        ui_view.ZoomAndCenterRectangle(zoom_viewCorner1, zoom_viewCorner2)

    def show_opening_btn_click(self, sender, e):
        try:
            self.show_opening(current=True)
        except Exception as ex:
            print(ex)

    def show_previous_location_btn_click(self, sender, e):
        try:
            self.show_opening(current=False)
        except Exception as ex:
            print(ex)


class ListBoxItemOpening(Windows.Controls.ListBoxItem):
    def __init__(self, opening, sizes):
        self.opening = opening

        self.grid = Windows.Controls.Grid()
        if self.opening["changeType"] == "added":
            self.grid.Background = Windows.Media.Brushes.LightGreen
        elif self.opening["changeType"] == "deleted":
            self.grid.Background = Windows.Media.Brushes.LightPink
        elif self.opening["changeType"] == "updated":
            self.grid.Background = Windows.Media.Brushes.LightYellow

        self.grid.Margin = Windows.Thickness(0, 0, 0, 2)

        for size in sizes:
            grid_column = Windows.Controls.ColumnDefinition()
            self.grid.ColumnDefinitions.Add(grid_column)
            grid_column.Width = Windows.GridLength(size)

        data_key_list = [
            "discipline",
            "mark",
            "changeType",
            "currentScheduledLevel",
            "isFloorOpening",
        ]
        for i, data_key in enumerate(data_key_list):
            text_block = Windows.Controls.TextBlock()

            text = ""
            if data_key == "isFloorOpening":
                if self.opening[data_key] is None:
                    text = ""
                elif self.opening[data_key]:
                    text = "Yes"
                else:
                    text = "No"
            else:
                text = self.opening[data_key] if data_key in self.opening else ""

            text_block.Text = text

            text_block.HorizontalAlignment = Windows.HorizontalAlignment.Center
            text_block.VerticalAlignment = Windows.VerticalAlignment.Center
            self.grid.Children.Add(text_block)
            Windows.Controls.Grid.SetColumn(text_block, i)

        self.Content = self.grid
