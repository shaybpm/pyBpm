# -*- coding: utf-8 -*-

import clr

clr.AddReferenceByPartialName("System")
clr.AddReference("System.Windows.Forms")
clr.AddReference("IronPython.Wpf")

from System import DateTime, TimeZoneInfo
import wpf
from System import Windows
import os

from ServerUtils import get_openings_changes  # type: ignore

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


class TrackingOpeningsDialog(Windows.Window):
    def __init__(self, doc):
        wpf.LoadComponent(self, xaml_file)

        self.doc = doc

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

        # TODO: FILTERS
        # level_filter_ComboBox
        # shape_filter_ComboBox
        # discipline_filter_ComboBox
        # floor_filter_ComboBox

        self.level_filter_ComboBox.Items.Add("All Levels")
        self.level_filter_ComboBox.SelectedIndex = 0

        self.shape_filter_ComboBox.Items.Add("All Shapes")
        self.shape_filter_ComboBox.SelectedIndex = 0

        self.discipline_filter_ComboBox.Items.Add("All Disciplines")
        self.discipline_filter_ComboBox.SelectedIndex = 0

        self.floor_filter_ComboBox.Items.Add("Walls And Floors")
        self.floor_filter_ComboBox.SelectedIndex = 0

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

    def data_listbox_selection_changed(self, sender, e):
        list_box = sender
        selected_items = [item.opening for item in list_box.SelectedItems]
        self.current_selected_opening = selected_items

    def update_more_data_info(self):
        if len(self.current_selected_opening) != 1:
            return
        opening = self.current_selected_opening[0]
        self.more_info_internalDocId_TextBlock.Text = str(opening["internalDocId"])
        self.more_info_isNotThereMoreUpdatedStates_TextBlock.Text = str(
            not opening["isThereMoreUpdatedStates"]
        )
        self.more_info_isFloorOpening_TextBlock.Text = (
            "Yes" if opening["isFloorOpening"] else "No"
        )

        # TODO:
        # more_info_currentScheduledLevel_TextBlock
        # more_info_currentShape_TextBlock
        # more_info_currentMct_TextBlock
        # more_info_lastScheduledLevel_TextBlock
        # more_info_lastShape_TextBlock
        # more_info_lastMct_TextBlock
        # x_location_changes_TextBlock
        # y_location_changes_TextBlock
        # z_location_changes_TextBlock

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
            key=lambda k: int(k[key])
            if type(k[key]) is str and k[key].isdigit()
            else k[key],
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


# example of openings:
# openings = [
#     {
#         "lastScheduledLevel": None,
#         "currentShape": None,
#         "discipline": "E",
#         "currentMct": None,
#         "_id": "65b8e34d5497961932dec70b",
#         "changeType": "deleted",
#         "internalDocId": 1910275,
#         "currentBBox": None,
#         "mark": "2",
#         "lastShape": None,
#         "uniqueId": "1b446db6-31d7-48bd-9893-092057fd3381-001d2603",
#         "isFloorOpening": False,
#         "deletedAt": "2024-01-30T11:54:14.195Z",
#         "lastBBox": None,
#         "lastMct": None,
#         "currentScheduledLevel": None,
#         "isThereMoreUpdatedStates": False,
#         "isDeleted": True,
#     },
#     {
#         "lastScheduledLevel": None,
#         "currentShape": None,
#         "discipline": "E",
#         "currentMct": None,
#         "_id": "65b8e34d5497961932dec70d",
#         "changeType": "deleted",
#         "internalDocId": 1912473,
#         "currentBBox": None,
#         "mark": "7",
#         "lastShape": None,
#         "uniqueId": "53f9eff0-b4e8-4f95-9f2c-02b56a1d1cbf-001d2e99",
#         "isFloorOpening": True,
#         "deletedAt": "2024-01-30T12:23:45.193Z",
#         "lastBBox": None,
#         "lastMct": None,
#         "currentScheduledLevel": None,
#         "isThereMoreUpdatedStates": False,
#         "isDeleted": True,
#     },
#     {
#         "lastScheduledLevel": None,
#         "currentShape": None,
#         "discipline": "E",
#         "currentMct": None,
#         "_id": "65b8e36b5497961932dec716",
#         "changeType": "deleted",
#         "internalDocId": 1912502,
#         "currentBBox": None,
#         "mark": "2",
#         "lastShape": None,
#         "uniqueId": "59a56166-fd50-427f-a8ff-56ba95383a3a-001d2eb6",
#         "isFloorOpening": True,
#         "deletedAt": "2024-01-30T12:23:45.193Z",
#         "lastBBox": None,
#         "lastMct": None,
#         "currentScheduledLevel": None,
#         "isThereMoreUpdatedStates": False,
#         "isDeleted": True,
#     },
#     {
#         "lastScheduledLevel": None,
#         "currentShape": "circular",
#         "discipline": "E",
#         "currentMct": False,
#         "_id": "65b8ea595497961932dec727",
#         "changeType": "added",
#         "internalDocId": 1903714,
#         "currentBBox": {
#             "max": {
#                 "z": 14.107611548556445,
#                 "y": 33.353914375793082,
#                 "x": 102.13648721403683,
#             },
#             "min": {
#                 "z": 13.779527559055106,
#                 "y": 33.025830386291595,
#                 "x": 101.31627724028321,
#             },
#         },
#         "mark": "1",
#         "lastShape": None,
#         "uniqueId": "ea127f05-3e56-403d-b980-29aad8edcc2e-001d0c62",
#         "isFloorOpening": False,
#         "currentScheduledLevel": "00",
#         "lastBBox": None,
#         "lastMct": None,
#         "isThereMoreUpdatedStates": False,
#         "isDeleted": False,
#     },
#     {
#         "lastScheduledLevel": None,
#         "currentShape": "circular",
#         "discipline": "E",
#         "currentMct": False,
#         "_id": "65b8ea595497961932dec729",
#         "changeType": "added",
#         "internalDocId": 1909917,
#         "currentBBox": {
#             "max": {
#                 "z": 13.287401574803289,
#                 "y": 34.469399940097553,
#                 "x": 92.184652872196736,
#             },
#             "min": {
#                 "z": 12.467191601049681,
#                 "y": 34.141315950596073,
#                 "x": 91.856568882695399,
#             },
#         },
#         "mark": "4",
#         "lastShape": None,
#         "uniqueId": "8081ce52-d981-4c40-9767-9c2b68710e59-001d249d",
#         "isFloorOpening": True,
#         "currentScheduledLevel": "00",
#         "lastBBox": None,
#         "lastMct": None,
#         "isThereMoreUpdatedStates": False,
#         "isDeleted": False,
#     },
#     {
#         "lastScheduledLevel": None,
#         "currentShape": "rectangular",
#         "discipline": "E",
#         "currentMct": False,
#         "_id": "65b8ea595497961932dec72b",
#         "changeType": "added",
#         "internalDocId": 1910394,
#         "currentBBox": {
#             "max": {
#                 "z": 14.435695538057757,
#                 "y": 36.634754270806219,
#                 "x": 102.13648721403671,
#             },
#             "min": {
#                 "z": 13.451443569553794,
#                 "y": 35.978586291803559,
#                 "x": 101.31627724028326,
#             },
#         },
#         "mark": "3",
#         "lastShape": None,
#         "uniqueId": "30c9be85-2877-4c4b-b5f5-189c164c1380-001d267a",
#         "isFloorOpening": True,
#         "currentScheduledLevel": "None",
#         "lastBBox": None,
#         "lastMct": None,
#         "isThereMoreUpdatedStates": False,
#         "isDeleted": False,
#     },
# ]
