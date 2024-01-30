# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
clr.AddReference("IronPython.Wpf")

import wpf
from System import Windows
import os


xaml_file = os.path.join(os.path.dirname(__file__), "TrackingOpeningsDialogUi.xaml")


class TrackingOpeningsDialog(Windows.Window):
    def __init__(self, doc):
        wpf.LoadComponent(self, xaml_file)
        self.doc = doc

        self.start_date_DatePicker.SelectedDateChanged += (
            self.start_date_DatePicker_SelectedDateChanged
        )
        self.start_hour_ComboBox.SelectionChanged += (
            self.start_hour_ComboBox_SelectionChanged
        )
        self.start_minute_ComboBox.SelectionChanged += (
            self.start_minute_ComboBox_SelectionChanged
        )

        self.end_date_DatePicker.SelectedDateChanged += (
            self.end_date_DatePicker_SelectedDateChanged
        )
        self.end_hour_ComboBox.SelectionChanged += (
            self.end_hour_ComboBox_SelectionChanged
        )
        self.end_minute_ComboBox.SelectionChanged += (
            self.end_minute_ComboBox_SelectionChanged
        )

    def start_date_DatePicker_SelectedDateChanged(self, sender, e):
        print("start_date_DatePicker_SelectedDateChanged")
        print("value: {}".format(self.start_date_DatePicker.SelectedDate.Date))

    def start_hour_ComboBox_SelectionChanged(self, sender, e):
        print("start_hour_ComboBox_SelectionChanged")
        print("value: {}".format(self.start_hour_ComboBox.SelectedValue))

    def start_minute_ComboBox_SelectionChanged(self, sender, e):
        print("start_minute_ComboBox_SelectionChanged")
        print("value: {}".format(self.start_minute_ComboBox.SelectedValue))

    def end_date_DatePicker_SelectedDateChanged(self, sender, e):
        print("end_date_DatePicker_SelectedDateChanged")
        print("value: {}".format(self.end_date_DatePicker.SelectedDate.Date))

    def end_hour_ComboBox_SelectionChanged(self, sender, e):
        print("end_hour_ComboBox_SelectionChanged")
        print("value: {}".format(self.end_hour_ComboBox.SelectedValue))

    def end_minute_ComboBox_SelectionChanged(self, sender, e):
        print("end_minute_ComboBox_SelectionChanged")
        print("value: {}".format(self.end_minute_ComboBox.SelectedValue))

    def get_dates_by_latest_sheet_versions_btn_click(self, sender, e):
        pass

    def show_openings_btn_click(self, sender, e):
        pass
