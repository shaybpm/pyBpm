# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from Autodesk.Revit.DB import XYZ

from System import DateTime, TimeZoneInfo, Windows
from pyrevit.framework import wpf
import os
import json

from pyrevit import forms, script

from ServerUtils import get_openings_changes, change_openings_approved_status
from RevitUtils import (
    convertRevitNumToCm,
    get_ui_view as ru_get_ui_doc,
    get_model_guids,
    get_level_by_point,
)
from ExcelUtils import create_new_workbook_file, add_data_to_worksheet
from UiUtils import SelectFromList

from FiltersInViewsDialog import FiltersInViewsDialog
import Utils
from SpecificOpeningFilterChanger import SpecificOpeningFilterChanger
from EventHandlers import (
    show_opening_3d_event,
    create_revision_clouds_event,
    filters_in_views_event,
)
from ReusableExternalEvents import (
    turn_on_isolate_mode_event,
    turn_off_isolate_mode_event,
)
from ExternalEventDataFile import ExternalEventDataFile

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

        self.setting_data_file_path = script.get_universal_data_file(
            file_id="settings",
            file_ext="json",
            add_cmd_name=True,
        )

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
        self.data_table_col_sizes = [64, 48, 80, 120, 120, 40]
        self.data_table_col_sizes.append(700 - 58 - sum(self.data_table_col_sizes))
        (
            self.sort_discipline_btn,
            self.sort_mark_btn,
            self.sort_changeType_btn,
            self.sort_scheduleLevel_btn,
            self.sort_realLevel_btn,
            self.sort_floor_btn,
            self.sort_approved_btn,
        ) = self.init_title_data_grid()

        self.data_listbox.SelectionChanged += self.data_listbox_selection_changed

        self.ALL_LEVELS = "All Levels"
        self.ALL_SHAPES = "All Shapes"
        self.ALL_DISCIPLINES = "All Disciplines"
        self.FLOORS_AND_WALLS = "Floors and Walls"
        self.set_all_filters()

        self.handle_buttons_state()

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
        for opening in value:
            bbox = Utils.get_bbox(self.doc, opening, current=True, prompt_alert=False)
            if bbox:
                center_point = XYZ(
                    (bbox.Min.X + bbox.Max.X) / 2,
                    (bbox.Min.Y + bbox.Max.Y) / 2,
                    (bbox.Min.Z + bbox.Max.Z) / 2,
                )
                currentLevel = get_level_by_point(center_point, self.doc, True)
                opening["currentRealLevel"] = currentLevel.Name if currentLevel else "-"
            else:
                opening["currentRealLevel"] = "-"

        self._openings = value
        self.display_openings = value
        self.number_of_data_TextBlock.Text = str(len(self._openings))
        self.set_all_filters()
        self.handle_buttons_state()

    @property
    def current_selected_opening(self):
        return self._current_selected_opening

    @current_selected_opening.setter
    def current_selected_opening(self, value):
        self._current_selected_opening = value
        self.update_more_data_info()
        self.handle_buttons_state()

    @property
    def current_sort_key(self):
        return self._current_sort_key

    @current_sort_key.setter
    def current_sort_key(self, value):

        self._current_sort_key = value
        self.sort_discipline_btn.Background = Windows.Media.Brushes.White
        self.sort_mark_btn.Background = Windows.Media.Brushes.White
        self.sort_changeType_btn.Background = Windows.Media.Brushes.White
        self.sort_scheduleLevel_btn.Background = Windows.Media.Brushes.White
        self.sort_realLevel_btn.Background = Windows.Media.Brushes.White
        self.sort_floor_btn.Background = Windows.Media.Brushes.White
        self.sort_approved_btn.Background = Windows.Media.Brushes.White
        if value is None:
            return
        sort_color = (
            Windows.Media.Brushes.LightBlue
            if not value.endswith("_REVERSE")
            else Windows.Media.Brushes.LightPink
        )
        _value = value.replace("_REVERSE", "")
        if _value == "discipline":
            self.sort_discipline_btn.Background = sort_color
            return
        if _value == "mark":
            self.sort_mark_btn.Background = sort_color
            return
        if _value == "changeType":
            self.sort_changeType_btn.Background = sort_color
            return
        if _value == "currentScheduledLevel":
            self.sort_scheduleLevel_btn.Background = sort_color
            return
        if _value == "currentRealLevel":
            self.sort_realLevel_btn.Background = sort_color
            return
        if _value == "isFloorOpening":
            self.sort_floor_btn.Background = sort_color
            return
        if _value == "approved":
            self.sort_approved_btn.Background = sort_color

    def alert(self, message):
        self.Hide()
        forms.alert(message, title="מעקב פתחים")
        self.Show()

    def handle_buttons_state(self):
        self.show_opening_btn.IsEnabled = True
        self.show_opening_3D_btn.IsEnabled = True
        self.create_cloud_btn.IsEnabled = True
        self.show_previous_location_btn.IsEnabled = True
        self.show_previous_location_3D_btn.IsEnabled = True
        self.isolate_btn.IsEnabled = True
        self.change_approved_status_btn.IsEnabled = True
        self.export_to_excel_btn.IsEnabled = True
        self.filters_in_views_btn.IsEnabled = True

        if len(self.openings) == 0:
            self.export_to_excel_btn.IsEnabled = False
            self.show_opening_btn.IsEnabled = False
            self.show_previous_location_btn.IsEnabled = False
            self.show_opening_3D_btn.IsEnabled = False
            self.show_previous_location_3D_btn.IsEnabled = False
            self.create_cloud_btn.IsEnabled = False
            self.change_approved_status_btn.IsEnabled = False

        if len(self.current_selected_opening) == 0:
            self.show_opening_btn.IsEnabled = False
            self.show_previous_location_btn.IsEnabled = False
            self.show_opening_3D_btn.IsEnabled = False
            self.show_previous_location_3D_btn.IsEnabled = False
            self.create_cloud_btn.IsEnabled = False
            self.change_approved_status_btn.IsEnabled = False

        if len(self.current_selected_opening) > 1:
            self.show_opening_btn.IsEnabled = False
            self.show_previous_location_btn.IsEnabled = False
            self.show_opening_3D_btn.IsEnabled = False
            self.show_previous_location_3D_btn.IsEnabled = False

    def set_all_filters(self):
        self.level_filter_ComboBox.Items.Clear()
        self.level_filter_ComboBox.Items.Add(self.ALL_LEVELS)
        self.level_filter_ComboBox.SelectedIndex = 0
        all_real_levels = {x["currentRealLevel"] for x in self.openings}
        all_real_levels = sorted(all_real_levels)
        for level in all_real_levels:
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

        self.changeType_filter_ComboBox.Items.Clear()
        self.changeType_filter_ComboBox.Items.Add("All Changes")
        self.changeType_filter_ComboBox.SelectedIndex = 0
        self.changeType_filter_ComboBox.Items.Add("added")
        self.changeType_filter_ComboBox.Items.Add("updated")
        self.changeType_filter_ComboBox.Items.Add("deleted")

        self.approved_status_options = [
            "approved",
            "approved but later modified",
            "not approved",
            "not treated",
            "conditionally approved",
        ]
        self.approved_filter_ComboBox.Items.Clear()
        self.approved_filter_ComboBox.Items.Add("All Approved")
        self.approved_filter_ComboBox.SelectedIndex = 0
        for opt in self.approved_status_options:
            self.approved_filter_ComboBox.Items.Add(opt)

    def level_filter_ComboBox_SelectionChanged(self, sender, e):
        self.filter_openings()

    def shape_filter_ComboBox_SelectionChanged(self, sender, e):
        self.filter_openings()

    def discipline_filter_ComboBox_SelectionChanged(self, sender, e):
        self.filter_openings()

    def floor_filter_ComboBox_SelectionChanged(self, sender, e):
        self.filter_openings()

    def changeType_filter_ComboBox_SelectionChanged(self, sender, e):
        self.filter_openings()

    def approved_filter_ComboBox_SelectionChanged(self, sender, e):
        self.filter_openings()

    def filter_openings(self):
        self.display_openings = self.openings
        if self.level_filter_ComboBox.SelectedIndex != 0:
            selected_level = self.level_filter_ComboBox.SelectedValue
            self.display_openings = [
                x
                for x in self.display_openings
                if x["currentRealLevel"] == selected_level
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
        if self.changeType_filter_ComboBox.SelectedIndex != 0:
            selected_changeType = self.changeType_filter_ComboBox.SelectedValue
            self.display_openings = [
                x
                for x in self.display_openings
                if x["changeType"] == selected_changeType
            ]
        if self.approved_filter_ComboBox.SelectedIndex != 0:
            selected_approved = self.approved_filter_ComboBox.SelectedValue
            self.display_openings = [
                x for x in self.display_openings if x["approved"] == selected_approved
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
        sort_scheduleLevel_btn.Content = "Schedule Level"
        sort_scheduleLevel_btn.Click += self.sort_scheduleLevel_btn_click
        sort_scheduleLevel_btn.Background = Windows.Media.Brushes.White
        grid.Children.Add(sort_scheduleLevel_btn)
        Windows.Controls.Grid.SetColumn(sort_scheduleLevel_btn, 3)

        sort_realLevel_btn = Windows.Controls.Button()
        sort_realLevel_btn.Content = "Real Level"
        sort_realLevel_btn.Click += self.sort_realLevel_btn_click
        sort_realLevel_btn.Background = Windows.Media.Brushes.White
        grid.Children.Add(sort_realLevel_btn)
        Windows.Controls.Grid.SetColumn(sort_realLevel_btn, 4)

        sort_floor_btn = Windows.Controls.Button()
        sort_floor_btn.Content = "Floor"
        sort_floor_btn.Click += self.sort_floor_btn_click
        sort_floor_btn.Background = Windows.Media.Brushes.White
        grid.Children.Add(sort_floor_btn)
        Windows.Controls.Grid.SetColumn(sort_floor_btn, 5)

        sort_approved_btn = Windows.Controls.Button()
        sort_approved_btn.Content = "Approved"
        sort_approved_btn.Click += self.sort_approved_btn_click
        sort_approved_btn.Background = Windows.Media.Brushes.White
        grid.Children.Add(sort_approved_btn)
        Windows.Controls.Grid.SetColumn(sort_approved_btn, 6)

        return (
            sort_discipline_btn,
            sort_mark_btn,
            sort_changeType_btn,
            sort_scheduleLevel_btn,
            sort_realLevel_btn,
            sort_floor_btn,
            sort_approved_btn,
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
            self.current_sort_key += "_REVERSE"
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

    def sort_realLevel_btn_click(self, sender, e):
        self.sort_data_by("currentRealLevel")

    def sort_floor_btn_click(self, sender, e):
        self.sort_data_by("isFloorOpening")

    def sort_approved_btn_click(self, sender, e):
        self.sort_data_by("approved")

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

    def start_date_long_ago_btn_click(self, sender, e):
        """update the start date to 10 years ago"""
        time_now = DateTime.Now
        time_10_years_ago = time_now.AddYears(-10)
        self.start_date_DatePicker.SelectedDate = time_10_years_ago
        self.start_hour_ComboBox.SelectedValue = "00"
        self.start_minute_ComboBox.SelectedValue = "00"
        self.update_start_date()

    def end_date_now_btn_click(self, sender, e):
        """update the end date to now"""
        time_now = DateTime.Now
        self.end_date_DatePicker.SelectedDate = time_now
        self.end_hour_ComboBox.SelectedValue = time_now.ToString("HH")
        self.end_minute_ComboBox.SelectedValue = time_now.ToString("mm")
        self.update_end_date()

    def show_openings_btn_click(self, sender, e):
        try:
            model_guids = get_model_guids(self.doc)
            self.openings = get_openings_changes(
                self.doc, self.start_time_str, self.end_time_str, model_guids
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

            self.current_sort_key = None
        except Exception as ex:
            print(ex)

    def get_current_selected_opening_if_one(self):
        if len(self.current_selected_opening) != 1:
            self.alert("יש לבחור פתח אחד בלבד")
            return
        return self.current_selected_opening[0]

    def get_ui_view(self):
        ui_view = ru_get_ui_doc(self.uidoc)
        if not ui_view:
            self.alert("לא נמצא מבט פעיל")
            return
        return ui_view

    def show_opening(self, current):
        opening = self.get_current_selected_opening_if_one()
        if not opening:
            return

        bbox = Utils.get_bbox(self.doc, opening, current)
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

    def show_opening_3d(self, current):
        ex_event_file = ExternalEventDataFile(self.doc)
        opening = self.get_current_selected_opening_if_one()
        if not opening:
            return
        ex_event_file.set_key_value("current_selected_opening", opening)
        ex_event_file.set_key_value("current_bool_arg", current)
        show_opening_3d_event.Raise()

    def show_opening_3D_btn_click(self, sender, e):
        try:
            self.show_opening_3d(current=True)
        except Exception as ex:
            print(ex)

    def show_previous_location_3D_btn_click(self, sender, e):
        try:
            self.show_opening_3d(current=False)
        except Exception as ex:
            print(ex)

    def create_revision_clouds(self):
        ex_event_file = ExternalEventDataFile(self.doc)
        ex_event_file.set_key_value(
            "current_selected_opening", self.current_selected_opening
        )
        create_revision_clouds_event.Raise()

    def create_cloud_btn_click(self, sender, e):
        try:
            self.create_revision_clouds()
        except Exception as ex:
            print(ex)

    def isolate_btn_mouse_down(self, sender, e):
        active_view = self.uidoc.ActiveView
        if not active_view:
            self.alert("לא נמצא מבט פעיל")
            return
        if active_view.IsTemporaryViewPropertiesModeEnabled():
            return
        if not active_view.CanEnableTemporaryViewPropertiesMode():
            self.alert("לא זמין במבט הנוכחי.")
            return
        try:
            turn_on_isolate_mode_event.Raise()
        except Exception as ex:
            print(ex)

    def isolate_btn_mouse_up(self, sender, e):
        active_view = self.uidoc.ActiveView
        if not active_view:
            self.alert("לא נמצא מבט פעיל")
            return
        if not active_view.IsTemporaryViewPropertiesModeEnabled():
            return
        try:
            turn_off_isolate_mode_event.Raise()
        except Exception as ex:
            print(ex)

    def zoom_ui_view(self, value):
        ui_view = self.get_ui_view()
        if not ui_view:
            self.alert("מבט לא נמצא")
            return
        ui_view.Zoom(value)

    def zoom_in_btn_click(self, sender, e):
        self.zoom_ui_view(1.1)

    def zoom_out_btn_click(self, sender, e):
        self.zoom_ui_view(0.9)

    def change_view_btn_click(self, sender, e):
        try:
            self.Hide()
            selected_view = forms.select_views(
                title="החלף מבט", multiple=False, button_name="בחר מבט"
            )
            self.Show()
            if not selected_view:
                return
            self.uidoc.ActiveView = selected_view
        except Exception as ex:
            print(ex)

    def set_change_approved_status_password(self):
        self.Hide()
        password = forms.ask_for_string(
            default="", prompt="הכנס סיסמה לשינוי סטטוס אישור", title="מעקב פתחים"
        )
        self.Show()
        if password is None:
            return None
        if os.path.exists(self.setting_data_file_path):
            with open(self.setting_data_file_path, "r") as file:
                data = json.load(file)
                data["change_approved_status_password"] = password
                with open(self.setting_data_file_path, "w") as file:
                    json.dump(data, file)
        else:
            with open(self.setting_data_file_path, "w") as file:
                json.dump({"change_approved_status_password": password}, file)
        return password

    def get_change_approved_status_password(self):
        if os.path.exists(self.setting_data_file_path):
            with open(self.setting_data_file_path, "r") as file:
                data = json.load(file)
                if "change_approved_status_password" in data:
                    return data["change_approved_status_password"]
                else:
                    return self.set_change_approved_status_password()
        else:
            return self.set_change_approved_status_password()

    def change_approved_status_btn_click(self, sender, e):
        if len(self.current_selected_opening) == 0:
            self.alert("יש לבחור פתחים")
            return

        password = self.get_change_approved_status_password()
        if password is None:
            return

        new_approved_status_options = [
            "approved",
            "not approved",
            "conditionally approved",
        ]

        select_from_list = SelectFromList(new_approved_status_options)
        new_approved_status = select_from_list.show()
        if new_approved_status is None:
            return

        specific_opening_filter_changer = SpecificOpeningFilterChanger(
            self.current_selected_opening, new_approved_status
        )

        new_status_list = Utils.get_new_opening_approved_status(
            self.current_selected_opening, new_approved_status
        )
        server_response = None
        try:
            server_response = change_openings_approved_status(
                self.doc, password, new_status_list
            )
        except Exception as ex:
            new_password = self.set_change_approved_status_password()
            if new_password is None:
                return
            try:
                server_response = change_openings_approved_status(
                    self.doc, new_password, new_status_list
                )
            except Exception as ex:
                if "403" in str(ex):
                    self.alert("סיסמה שגויה")
                else:
                    print(ex)
                return

        if server_response:
            response_unique_ids = [x["uniqueId"] for x in server_response]
            new_openings = list(self.openings)
            for opening in new_openings:
                if opening["uniqueId"] in response_unique_ids:
                    opening["approved"] = new_approved_status

            level_filter = self.level_filter_ComboBox.SelectedValue
            shape_filter = self.shape_filter_ComboBox.SelectedValue
            discipline_filter = self.discipline_filter_ComboBox.SelectedValue
            floor_filter = self.floor_filter_ComboBox.SelectedValue
            changeType_filter = self.changeType_filter_ComboBox.SelectedValue
            approved_filter = self.approved_filter_ComboBox.SelectedValue
            self.openings = new_openings
            self.level_filter_ComboBox.SelectedValue = level_filter
            self.shape_filter_ComboBox.SelectedValue = shape_filter
            self.discipline_filter_ComboBox.SelectedValue = discipline_filter
            self.floor_filter_ComboBox.SelectedValue = floor_filter
            self.changeType_filter_ComboBox.SelectedValue = changeType_filter
            self.approved_filter_ComboBox.SelectedValue = approved_filter
            self.filter_openings()

            specific_opening_filter_changer.change_filter(self.doc)

    def filters_in_views_btn_click(self, sender, e):
        try:
            filters_in_views_dialog = FiltersInViewsDialog(self.doc)
            if not filters_in_views_dialog.db_project_openings:
                self.alert("אין פתחים שאינם מאושרים בפרויקט")
                return
            self.Hide()
            filters_in_views_settings = filters_in_views_dialog.show_dialog()
            self.Show()
            if filters_in_views_settings is None:
                return
            ex_event_file = ExternalEventDataFile(self.doc)
            ex_event_file.set_key_value(
                "filters_in_views_settings", filters_in_views_settings
            )
            filters_in_views_event.Raise()
        except Exception as ex:
            print(ex)

    def export_to_excel_btn_click(self, sender, e):
        if not self.openings:
            self.alert("אין נתונים לייצוא")
            return
        self.Hide()
        folder_path = forms.pick_folder()
        self.Show()
        if not folder_path:
            return
        file_name = "pyBpm-Openings.xlsx"
        num = 1
        max_loops = 100
        while os.path.exists(folder_path + "\\" + file_name):
            file_name = "pyBpm-Openings_{}.xlsx".format(num)
            num += 1
            if num > max_loops:
                self.alert("מספר נסיונות מקסימלי ליצירת שם קובץ חדש, הקובץ לא נוצר")
                return
        try:
            excel_path = create_new_workbook_file(folder_path + "\\" + file_name)
            add_data_to_worksheet(excel_path, self.openings, ignore_fields=["_id"])
            self.Hide()
            is_to_open = forms.alert(
                "הקובץ נוצר בהצלחה.\nהאם לפתוח אותו?", title="מעקב פתחים"
            )
            self.Show()
            if is_to_open:
                os.startfile(excel_path)
        except Exception as ex:
            print(ex)


class ListBoxItemOpening(Windows.Controls.ListBoxItem):
    def __init__(self, opening, sizes):
        self.opening = opening

        self.grid = Windows.Controls.Grid()

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
            "currentRealLevel",
            "isFloorOpening",
            "approved",
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

            if data_key == "changeType":
                text_block.Padding = Windows.Thickness(4, 0, 4, 0)
                if text == "added":
                    text_block.Background = Windows.Media.Brushes.LightGreen
                elif text == "deleted":
                    text_block.Background = Windows.Media.Brushes.LightPink
                elif text == "updated":
                    text_block.Background = Windows.Media.Brushes.LightYellow

            if data_key == "approved":
                text_block.Padding = Windows.Thickness(4, 0, 4, 0)
                if text == "approved":
                    text_block.Background = Windows.Media.Brushes.LightGreen
                if text == "conditionally approved":
                    text_block.Background = Windows.Media.Brushes.LightBlue
                elif text == "approved but later modified":
                    text_block.Background = Windows.Media.Brushes.LightYellow
                elif text == "not approved":
                    text_block.Background = Windows.Media.Brushes.LightPink
                elif text == "not treated":
                    text_block.Background = Windows.Media.Brushes.LightGray

            self.grid.Children.Add(text_block)
            Windows.Controls.Grid.SetColumn(text_block, i)

        self.Content = self.grid
