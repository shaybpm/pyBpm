# -*- coding: utf-8 -*-
"""Text for WPF controls that must show it exactly as written.

CheckBox, RadioButton, Button, ToggleButton, Label, GroupBox, Expander, TabItem
and grid column headers read a string Content as a caption with a keyboard
shortcut: the first underscore marks the shortcut key and is not drawn, so a
filter named AC_Pipes shows as ACPipes. A TextBlock as the Content is drawn as
is, which is what any name from the model needs. Code that reads the label back
reads Content.Text.

ListBoxItem, ComboBoxItem, TreeViewItem and ToolTip do not do this.
"""

import clr

clr.AddReference("PresentationFramework")

from System.Windows.Controls import TextBlock


def plain_text(text):
    block = TextBlock()
    block.Text = u"" if text is None else u"{}".format(text)
    return block
