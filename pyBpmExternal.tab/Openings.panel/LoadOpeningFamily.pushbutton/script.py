# -*- coding: utf-8 -*-
""" Loads the BPM Opening family into the project. """
__title__ = 'Load Opening\nFamily'
__author__ = 'Ely Komm & Eyal Sinay'

# ------------------------------

import clr
clr.AddReference('RevitAPI')
clr.AddReferenceByPartialName('PresentationCore')
clr.AddReferenceByPartialName('AdWindows')
clr.AddReferenceByPartialName("PresentationFramework")
clr.AddReferenceByPartialName('System')
clr.AddReferenceByPartialName('System.Windows.Forms')

from Autodesk.Revit.UI import TaskDialog

max_elements = 5
gdict = globals()
uiapp = __revit__
uidoc = uiapp.ActiveUIDocument
if uidoc:
    doc = uiapp.ActiveUIDocument.Document

def alert(msg):
    TaskDialog.Show('BPM - Load Opening Family', msg)

# ------------------------------------------------------------
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
import LoadOpeningFamily
# ------------------------------------------------------------

LoadOpeningFamily.run()
