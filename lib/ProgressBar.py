# -*- coding: utf-8 -*-
"""Progress bar window implemented in IronPython.
This version mirrors the original C# logic but leverages
System.Action as the delegate passed to Dispatcher.Invoke.
"""

import clr

# Core WPF assemblies
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")
clr.AddReference("System.Windows.Forms")

# IronPython‑specific helper (try/except because it's optional in some envs)
try:
    clr.AddReference("IronPython.Wpf")
except Exception:
    pass

from pyrevit.framework import wpf
from System import Action
from System.Windows import (
    Window,
    Visibility,
    Forms,
    Media,
    Controls,
    Thickness,
    HorizontalAlignment,
)
from System.Windows.Threading import DispatcherPriority

import os

# Path to the companion XAML file that defines the UI
DIALOG_XAML = os.path.join(os.path.dirname(__file__), "ui", "ProgressBar.xaml")


class SubProgressBar:
    def __init__(self, sub_progress_bar_element, sub_loading_text):
        self.sub_progress_bar_element = sub_progress_bar_element
        self.sub_loading_text = sub_loading_text

        self.percent = 0.0
        self.message = ""


class ProgressBar(Window):
    """Simple progress‑bar window with optional cancel support."""

    def __init__(self, cancel_action=None, height=None):
        # Load the XAML UI layout
        wpf.LoadComponent(self, DIALOG_XAML)

        # Store the cancel callback (if any)
        self._cancel_action = cancel_action
        self._with_sub_progress = 0  # type: int

        # Title & progress state
        self._current_title = ""
        self._current_main_percent = 0.0
        self._current_main_message = ""

        self.subs = []  # type: list[SubProgressBar]

        self._current_index = -1

        # Hide the Cancel button when no callback provided
        if cancel_action is None:
            # self.Height = self.Height - 60
            self.CancelBtn.Visibility = Visibility.Hidden

        if height is not None:
            self.Height = height

        self.initialize_sub_progresses()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def current_title(self):
        return self._current_title

    @current_title.setter
    def current_title(self, value):
        self._current_title = value
        self.TitleText.Text = value
        self.Title = value

    @property
    def with_sub_progress(self):
        return self._with_sub_progress

    @with_sub_progress.setter
    def with_sub_progress(self, value):
        self._with_sub_progress = value
        self.initialize_sub_progresses()

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------
    def initialize_sub_progresses(self):
        """Initialize sub progress bar elements based on the with_sub_progress flag."""
        if self.with_sub_progress < 0:
            raise ValueError("with_sub_progress must be a non-negative integer")

        self.SubProgressPanel.Children.Clear()
        if self.with_sub_progress == 0:
            return

        # add separator line
        separator = Controls.Border()
        separator.BorderBrush = Media.Brushes.LightGray
        separator.Margin = Thickness(0, 0, 0, 8)
        separator.BorderThickness = Thickness(0, 1, 0, 0)
        separator.Height = 1
        self.SubProgressPanel.Children.Add(separator)

        self.subs = []
        for i in range(self.with_sub_progress):
            sub_progress_bar_element = Controls.ProgressBar()
            sub_progress_bar_element.Minimum = 0
            sub_progress_bar_element.Maximum = 100
            sub_progress_bar_element.Value = 0
            sub_progress_bar_element.Width = 200
            sub_progress_bar_element.Height = 20
            sub_progress_bar_element.Margin = Thickness(0, 16, 0, 0)

            sub_progress_bar_textbox = Controls.TextBox()
            sub_progress_bar_textbox.FontSize = 16
            sub_progress_bar_textbox.Foreground = Media.Brushes.White
            sub_progress_bar_textbox.Background = Media.Brushes.Transparent
            sub_progress_bar_textbox.HorizontalAlignment = HorizontalAlignment.Center
            sub_progress_bar_textbox.Margin = Thickness(0, 4, 0, 0)

            self.subs.append(
                SubProgressBar(sub_progress_bar_element, sub_progress_bar_textbox)
            )
            self.SubProgressPanel.Children.Add(sub_progress_bar_element)
            self.SubProgressPanel.Children.Add(sub_progress_bar_textbox)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_main_status(self, percent, message):
        """Thread‑safe update of the UI state.

        Can be called from any background thread.  We stash the state on the
        instance, then marshal the actual visual update onto the UI thread
        via Dispatcher.Invoke.
        """
        self._current_main_percent = percent
        self._current_main_message = message

        # Dispatcher.Invoke expects a System.Delegate with *no* parameters.
        # Wrapping the do_events method in System.Action satisfies that.
        self.Dispatcher.Invoke(
            Action(self._do_events_main),
            DispatcherPriority.Background,
        )

    def update_sub_status(self, index, percent, message):
        """Thread‑safe update of the sub progress bar state."""
        if index >= len(self.subs) or index < 0:
            raise IndexError("Sub progress index out of range: {}".format(index))

        sub = self.subs[index]
        sub.percent = percent
        sub.message = message

        self._current_index = index

        self.Dispatcher.Invoke(
            Action(self._do_events_sub),
            DispatcherPriority.Background,
        )

    def pre_set_main_status(self, main_message):
        self.update_main_status(0, main_message)

    def pre_set_sub_statuses(self, sub_messages=None):
        """Pre-set the main and sub progress bar statuses."""
        if sub_messages is not None:
            self.with_sub_progress = len(sub_messages)
            for i, message in enumerate(sub_messages):
                self.update_sub_status(i, 0, message)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _do_events_main(self):
        """Runs on the UI thread – actually updates the visuals."""
        self.MainProgressBarElement.Value = self._current_main_percent
        self.MainLoadingText.Text = self._current_main_message

    def _do_events_sub(self):
        """Runs on the UI thread – actually updates the visuals."""
        if self._current_index >= len(self.subs) or self._current_index < 0:
            raise IndexError(
                "self._current_index is out of range: {}".format(self._current_index)
            )

        sub = self.subs[self._current_index]
        sub.sub_progress_bar_element.Value = sub.percent
        sub.sub_loading_text.Text = sub.message

    def Cancel_Click(self, sender, _):
        if self._cancel_action is not None:
            self._cancel_action()
        self.Close()

    @staticmethod
    def exec_with_progressbar(
        func, title="Progress", cancelable=True, on_cancel=None, height=None
    ):
        def _func(sender, e):
            try:
                progress_bar = sender  # type: ProgressBar
                func(progress_bar)
            except UserCanceledException:
                if on_cancel:
                    on_cancel()
            except Exception as ex:
                print("An error occurred: {}".format(ex))
            finally:
                progress_bar.Close()

        def _cancel_func():
            raise UserCanceledException("User canceled the operation")

        cancel_func = _cancel_func if cancelable else None
        progress_bar = ProgressBar(cancel_func, height=height)
        progress_bar.current_title = title
        progress_bar.ContentRendered += _func
        progress_bar.ShowDialog()


class UserCanceledException(Exception):
    pass
