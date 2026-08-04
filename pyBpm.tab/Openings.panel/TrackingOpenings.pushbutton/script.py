# -*- coding: utf-8 -*-
""" RETIRED - Tracking Openings moved to BPMTools (BPM ribbon tab).

The bundle is kept (icon + button) on purpose, so users who click the familiar
button get an explanation instead of a missing button.
See OPENINGS_MIGRATION_PLAN.md par.12 and OPENINGS_REMOVAL_INSTRUCTIONS.md par.3. """
__title__ = "Tracking\nOpenings"
__author__ = "BPM"

from pyrevit import forms

forms.alert(
    "This tool has moved to BPMTools.\n\n"
    "Openings Tracking, Opening Set and Opening Explorer are now built into "
    "BPMTools, under the BPM ribbon tab.\n\n"
    "Don't see them? Update BPMTools (BPM tab > Check For Updates), or install it from:\n"
    "https://bondsstorageaccount.blob.core.windows.net/production/BPMTools/BPMTools.Installer.msi",
    title="Moved to BPMTools",
)
