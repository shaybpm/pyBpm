# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
import wpf
import os

xaml_file = os.path.join(os.path.dirname(__file__), "PyBpmInfoUi.xaml")


class PyBpmInfo(Windows.Window):
    def __init__(self):
        wpf.LoadComponent(self, xaml_file)
