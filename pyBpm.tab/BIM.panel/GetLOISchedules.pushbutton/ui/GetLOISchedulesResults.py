# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

# from Autodesk.Revit.DB import

from pyrevit.framework import wpf
from System import Windows
import os, sys

xaml_file = os.path.join(os.path.dirname(__file__), "GetLOISchedulesResults.xaml")


class GetLOISchedulesResults(Windows.Window):
    def __init__(self, uidoc, schedules):
        wpf.LoadComponent(self, xaml_file)
        self.uidoc = uidoc
        self.schedules = schedules

        self.h1_TextBlock.Text = "{} schedules loaded to your model.".format(
            len(self.schedules)
        )

        for schedule in self.schedules:
            schedule_button = Windows.Controls.Button()
            schedule_button.Content = schedule.Name
            schedule_button.Tag = schedule.Id.IntegerValue
            schedule_button.Click += self.schedule_button_Click

            self.main_StackPanel.Children.Add(schedule_button)

    def get_schedule_by_id_int(self, id_int):
        for schedule in self.schedules:
            if schedule.Id.IntegerValue == id_int:
                return schedule
        return None

    def schedule_button_Click(self, sender, e):
        try:
            schedule_id = sender.Tag
            schedule = self.get_schedule_by_id_int(schedule_id)
            if not schedule:
                return
            self.uidoc.ActiveView = schedule
        except Exception as ex:
            print(ex)
