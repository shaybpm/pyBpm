# -*- coding: utf-8 -*-

import clr

clr.AddReferenceByPartialName("System")
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("System.Windows.Forms")
clr.AddReference("IronPython.Wpf")

from System import Windows
import wpf
import os


xaml_file = os.path.join(os.path.dirname(__file__), "MepOpeningMonitorDialogUi.xaml")


class MepOpeningMonitorDialog(Windows.Window):
    def __init__(self, uidoc, results):
        wpf.LoadComponent(self, xaml_file)

        self.uidoc = uidoc
        self.doc = self.uidoc.Document
        self.results = results
