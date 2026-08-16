# -*- coding: utf-8 -*-
""" Shared "this tool moved to BPMTools" notice.

The retired Openings buttons (Tracking Openings / Opening Set / Opening Explorer)
all land here instead of running.

This module imports NOTHING at module level, and must stay that way. It is the
last thing standing between the user and a dead button, and an ImportError here
is raised while the button's script.py is still being imported - the caller has
no chance to catch it, so the user gets a traceback instead of the notice. That
is exactly what happened when System.Uri failed to resolve on a client engine
(T-0375). The window lives in MovedToBpmToolsUi, imported lazily below; anything
that goes wrong there degrades to a plain alert that still carries the URL.
"""

INSTALLER_URL = "https://bondsstorageaccount.blob.core.windows.net/production/BPMTools/BPMTools.Installer.msi"


def show_moved_to_bpmtools(extra_note=None):
    """Show the migration dialog. `extra_note` adds one tool-specific line."""
    try:
        import MovedToBpmToolsUi

        MovedToBpmToolsUi.show(INSTALLER_URL, extra_note)
    except Exception as ex:
        _fallback_alert(extra_note, ex)


def _fallback_alert(extra_note, ex):
    """Plain-text last resort - no WPF, no .NET beyond what pyRevit itself uses."""
    from pyrevit import forms

    lines = [
        "Openings Tracking, Opening Set and Opening Explorer are now built into "
        "BPMTools, under the BPM ribbon tab.",
    ]
    if extra_note:
        lines.append(extra_note)
    lines.append(
        "Already have BPMTools? Update it from the BPM tab > Check For Updates.\n"
        "Otherwise install it from:\n" + INSTALLER_URL
    )

    forms.alert(
        "\n\n".join(lines),
        title="Moved to BPMTools",
        sub_msg="(simplified view - {})".format(ex),
    )
