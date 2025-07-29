# -*- coding: utf-8 -*-

import webbrowser
import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from pyrevit.framework import wpf
import os
import PyBpmAppUtils

xaml_file = os.path.join(os.path.dirname(__file__), "PyBpmInfoUi.xaml")


class PyBpmInfo(Windows.Window):
    def __init__(self):
        wpf.LoadComponent(self, xaml_file)

        self.current_version = PyBpmAppUtils.get_current_version()
        self.latest_version = PyBpmAppUtils.get_latest_version()
        self.has_new_version = self.current_version != self.latest_version

        self.hebText = (
            "חברת BPM מספקת את pyBpm, תוסף לרוויט שנבנה במיוחד כדי לסייע לחברות שעובדות איתנו בתהליכי תכנון וניהול מודלי BIM. התוסף מאפשר לייעל את תהליכי העבודה, לשפר את איכות התוצרים ולחסוך בזמן."
            + "\n"
            + "\n"
            + "גרסה נוכחית: {}".format(self.current_version)
            + ".\n"
            + (
                "גרסה זו היא המעודכנת ביותר."
                if not self.has_new_version
                else "יש גרסה מעודכנת יותר: {}".format(self.latest_version)
                + ".\n"
                + "תוכל לעדכן על ידי לחיצה על כפתור Update."
            )
            + "\n"
            + "\n"
            + "מה חדש בגרסה זו:"
            + "\n"
            + "- תוקן באג בטעינת משפחות הפתחים."
        )
        self.engText = (
            "BPM offers pyBpm, an add-in for Revit that was built specifically to help companies working with us in BIM planning and management processes. The add-in allows you to streamline work processes, improve the quality of the products and save time."
            + "\n"
            + "\n"
            + "Current version: {}".format(self.current_version)
            + ".\n"
            + (
                "This is the most updated version."
                if not self.has_new_version
                else "There is a newer version: {}".format(self.latest_version)
                + ".\n"
                + "You can update by clicking the Update button."
            )
            + "\n"
            + "\n"
            + "What's new in this version:"
            + "\n"
            + "- Fixed a bug in loading opening families."
        )
        self.LanguageComboBox.SelectionChanged += self.LanguageComboBox_SelectionChanged
        self.AddText()

    def AddText(self):
        language = self.LanguageComboBox.SelectedItem.Content
        if language == "Hebrew":
            self.StaticTextBlock.Text = self.hebText
            self.ScrollViewer.FlowDirection = Windows.FlowDirection.RightToLeft
            self.HTD_Link.Content = "קישור למדריך"
            self.HTD_Link.HorizontalAlignment = Windows.HorizontalAlignment.Right
        else:
            self.StaticTextBlock.Text = self.engText
            self.ScrollViewer.FlowDirection = Windows.FlowDirection.LeftToRight
            self.HTD_Link.Content = "Link to the guide"
            self.HTD_Link.HorizontalAlignment = Windows.HorizontalAlignment.Left

    def LanguageComboBox_SelectionChanged(self, sender, e):
        self.AddText()

    def HTD_Link_Click(self, sender, e):
        webbrowser.open(
            "https://drive.google.com/file/d/1mwdQy_-TjNktYRjLJLK_RqIyEwO59chN/view?usp=drive_link"
        )

    def OkButton_Click(self, sender, e):
        self.Close()
