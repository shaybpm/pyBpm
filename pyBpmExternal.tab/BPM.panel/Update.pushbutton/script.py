# -*- coding: utf-8 -*-
""" Update pyBpmExternal Extension. """
__title__ = 'Update'
__author__ = 'Eyal Sinay'

# ------------------------------

import clr
clr.AddReference('RevitAPI')
clr.AddReferenceByPartialName('PresentationCore')
clr.AddReferenceByPartialName('AdWindows')
clr.AddReferenceByPartialName("PresentationFramework")
clr.AddReferenceByPartialName('System')
clr.AddReferenceByPartialName('System.Windows.Forms')

# from Autodesk.Revit.DB import Transaction
from Autodesk.Revit.UI import TaskDialog

max_elements = 5
gdict = globals()
uiapp = __revit__
uidoc = uiapp.ActiveUIDocument
if uidoc:
    doc = uiapp.ActiveUIDocument.Document

def alert(msg):
    TaskDialog.Show('BPM - Opening Update', msg)

# ------------------------------------------------------------

# ------------------------------------------------------------

def run():
    pass

run()
