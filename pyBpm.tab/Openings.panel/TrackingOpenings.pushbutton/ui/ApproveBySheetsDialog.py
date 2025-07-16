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

xaml_file = os.path.join(os.path.dirname(__file__), "ApproveBySheetsDialogUi.xaml")


class ApproveBySheetsDialog(Windows.Window):
    def __init__(self, doc):
        wpf.LoadComponent(self, xaml_file)
        self.doc = doc
        
        
    def ok_btn_click(self, sender, e):
        # Logic for OK button click
        self.Close()
        
    def cancel_btn_click(self, sender, e):
        # Logic for Cancel button click
        self.Close()