# -*- coding: utf-8 -*-
""" Home page for the Get Bpm Sections results window (R1).

The default page of SectionsResultsWindow. It shows only HOW MANY sheets and
sections were found and a short instruction - it computes NOTHING (decision D1).
The heavy per-sheet scoring happens lazily on a sheet page (R2). IronPython 2.7
/ WPF; Hebrew only inside string bodies. """

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from pyrevit.framework import wpf
import os

xaml_file = os.path.join(os.path.dirname(__file__), "SectionsHomePage.xaml")


class SectionsHomePage(Windows.Controls.Page):
    def __init__(self, res_window):
        wpf.LoadComponent(self, xaml_file)
        self.res_window = res_window
        self.update_content()

    def update_content(self):
        """(Re)build the static text. Called on open and whenever the sheet-gating
        state changes (a filter selection was saved from Settings)."""
        sheets = self.res_window.sheets
        items = self.res_window.items
        self.HeadingTextBlock.Text = u"התאמת חתכים - BPM"
        self.CountsTextBlock.Text = u"נמצאו {} גיליונות ו-{} חתכים.".format(
            len(sheets), len(items)
        )
        if self.res_window.has_filters():
            self.HintTextBlock.Text = (
                u"בחר גיליון מהתפריט בצד כדי לחשב את ההתאמה שלו."
            )
        else:
            self.HintTextBlock.Text = (
                u"בחר פילטרים בעמוד ההגדרות כדי לפתוח את הגיליונות."
            )
