# -*- coding: utf-8 -*-
""" WPF window for the "this tool moved to BPMTools" notice.

Kept apart from MovedToBpmTools on purpose: everything here can fail to import
(WPF assemblies, .NET namespaces), so it is imported lazily from there, inside a
try/except. Never import this module at the top of a script.py.

Nothing here may depend on System.Uri or any other name outside the WPF
assemblies referenced below - resolving System.Uri failed on a client engine and
took the whole notice down with it (T-0375).
"""
import clr

clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")

from System.Windows import (
    Window,
    Thickness,
    TextWrapping,
    WindowStartupLocation,
    WindowStyle,
    ResizeMode,
    SizeToContent,
    HorizontalAlignment,
    VerticalAlignment,
    FontWeights,
    Clipboard,
)
from System.Windows.Controls import TextBlock, Button, StackPanel, Border, Orientation
from System.Windows.Documents import Hyperlink, Run
from System.Windows.Media import Brushes, SolidColorBrush, Color

_ACCENT = Color.FromRgb(11, 111, 203)
_ACCENT_DARK = Color.FromRgb(8, 88, 162)
_HEADER_BG = Color.FromRgb(245, 247, 250)
_BORDER = Color.FromRgb(222, 226, 230)


def _brush(color):
    return SolidColorBrush(color)


def _open_url(url):
    """Open a URL with the user's default browser (Revit 2025+ safe).

    Two ways in, because reaching the installer is the entire point of this
    window: System.Diagnostics may not resolve on every engine, and os.startfile
    goes through the shell without it.
    """
    try:
        from PyRevitUtils import start_process

        start_process(url)
    except Exception:
        import os

        os.startfile(url)


class MovedToBpmToolsWindow(Window):
    def __init__(self, url, extra_note=None):
        self.url = url
        self.extra_note = extra_note
        self._build()

    def _build(self):
        self.Title = "Moved to BPMTools"
        self.Width = 520
        self.SizeToContent = SizeToContent.Height
        self.ResizeMode = ResizeMode.NoResize
        self.WindowStyle = WindowStyle.SingleBorderWindow
        self.WindowStartupLocation = WindowStartupLocation.CenterScreen
        self.ShowInTaskbar = False
        self.Topmost = True
        self.Background = Brushes.White

        root = StackPanel()

        # --- header strip ---
        header_text = TextBlock()
        header_text.Text = "This tool has moved to BPMTools"
        header_text.FontSize = 17
        header_text.FontWeight = FontWeights.SemiBold
        header_text.TextWrapping = TextWrapping.Wrap
        header_text.Margin = Thickness(20, 16, 20, 16)

        header = Border()
        header.Background = _brush(_HEADER_BG)
        header.BorderBrush = _brush(_BORDER)
        header.BorderThickness = Thickness(0, 0, 0, 1)
        header.Child = header_text
        root.Children.Add(header)

        body = StackPanel()
        body.Margin = Thickness(20, 16, 20, 18)

        body.Children.Add(
            self._paragraph(
                "Openings Tracking, Opening Set and Opening Explorer are now built "
                "into BPMTools, under the BPM ribbon tab."
            )
        )

        if self.extra_note:
            body.Children.Add(self._paragraph(self.extra_note))

        body.Children.Add(
            self._paragraph(
                "Already have BPMTools? Update it from the BPM tab > Check For Updates."
            )
        )

        body.Children.Add(
            self._paragraph("Otherwise, install it - one click, no browser needed:")
        )

        # --- primary action ---
        download_btn = Button()
        download_btn.Content = "Download BPMTools Installer"
        download_btn.FontSize = 14
        download_btn.FontWeight = FontWeights.SemiBold
        download_btn.Foreground = Brushes.White
        download_btn.Background = _brush(_ACCENT)
        download_btn.BorderBrush = _brush(_ACCENT_DARK)
        download_btn.BorderThickness = Thickness(1)
        download_btn.Padding = Thickness(18, 9, 18, 9)
        download_btn.HorizontalAlignment = HorizontalAlignment.Left
        download_btn.Margin = Thickness(0, 4, 0, 10)
        download_btn.Cursor = self._hand_cursor()
        download_btn.Click += self.download_Click
        body.Children.Add(download_btn)

        # --- the raw link, clickable, so it also works if the button is blocked.
        #     Click, not RequestNavigate: RequestNavigate needs a NavigateUri,
        #     and building one needs System.Uri - the import that broke T-0375.
        link_block = TextBlock()
        link_block.TextWrapping = TextWrapping.Wrap
        link_block.FontSize = 11
        link_block.Foreground = Brushes.Gray
        link_block.Margin = Thickness(0, 0, 0, 4)
        link_block.Inlines.Add(Run("Direct link: "))

        link = Hyperlink(Run(self.url))
        link.Click += self.link_Click
        link_block.Inlines.Add(link)
        body.Children.Add(link_block)

        # --- footer buttons ---
        footer = StackPanel()
        footer.Orientation = Orientation.Horizontal
        footer.HorizontalAlignment = HorizontalAlignment.Right
        footer.Margin = Thickness(0, 12, 0, 0)

        self.copy_btn = Button()
        self.copy_btn.Content = "Copy link"
        self.copy_btn.Padding = Thickness(12, 5, 12, 5)
        self.copy_btn.Margin = Thickness(0, 0, 8, 0)
        self.copy_btn.Cursor = self._hand_cursor()
        self.copy_btn.Click += self.copy_Click
        footer.Children.Add(self.copy_btn)

        close_btn = Button()
        close_btn.Content = "Close"
        close_btn.Padding = Thickness(18, 5, 18, 5)
        close_btn.IsDefault = True
        close_btn.IsCancel = True
        close_btn.Cursor = self._hand_cursor()
        close_btn.Click += self.close_Click
        footer.Children.Add(close_btn)

        body.Children.Add(footer)
        root.Children.Add(body)

        self.Content = root

    def _paragraph(self, text):
        block = TextBlock()
        block.Text = text
        block.TextWrapping = TextWrapping.Wrap
        block.FontSize = 13
        block.Margin = Thickness(0, 0, 0, 10)
        block.VerticalAlignment = VerticalAlignment.Top
        return block

    def _hand_cursor(self):
        from System.Windows.Input import Cursors

        return Cursors.Hand

    # -- handlers: any exception escaping a WPF handler kills Revit, so all of
    #    them swallow and report instead of raising.
    def download_Click(self, sender, e):
        try:
            _open_url(self.url)
            self.Close()
        except Exception as ex:
            self._report_error(ex)

    def link_Click(self, sender, e):
        try:
            _open_url(self.url)
            self.Close()
        except Exception as ex:
            self._report_error(ex)

    def copy_Click(self, sender, e):
        try:
            Clipboard.SetText(self.url)
            self.copy_btn.Content = "Copied!"
        except Exception as ex:
            self._report_error(ex)

    def close_Click(self, sender, e):
        try:
            self.Close()
        except Exception:
            pass

    def _report_error(self, ex):
        from pyrevit import forms

        forms.alert(
            "Could not open the download link automatically.\n\n"
            "Please copy this address into your browser:\n" + self.url,
            title="Moved to BPMTools",
            sub_msg=str(ex),
        )


def show(url, extra_note=None):
    MovedToBpmToolsWindow(url, extra_note).ShowDialog()
