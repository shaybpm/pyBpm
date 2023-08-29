# -*- coding: utf-8 -*-
""" This script iterates over all the openings (Generic Model from the BPM library) and dose the following:
- Copies the Elevation to a taggable parameter (useful in versions 20+21).
- Copies the Reference Level to a taggable parameter.
- Sets Mark to opening if it is missing.
- Defines whether the opening is located in the floor or not.
- Calculates the projected height of the opening.
- Calculates the absolute height of the opening. """
__title__ = 'Opening\nSetter'
__author__ = ['Ely Komm', 'Eyal Sinay']

# ------------------------------

import clr
clr.AddReference('RevitAPI')
clr.AddReferenceByPartialName('PresentationCore')
clr.AddReferenceByPartialName('AdWindows')
clr.AddReferenceByPartialName("PresentationFramework")
clr.AddReferenceByPartialName('System')
clr.AddReferenceByPartialName('System.Windows.Forms')

from Autodesk.Revit.DB import Transaction
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
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
import OpeningSetter
# ------------------------------------------------------------

def run():
    all_openings = OpeningSetter.get_all_openings(doc)
    if len(all_openings) == 0:
        alert('No openings found.')
        return
    
    t = Transaction(doc, 'BPM | Opening Update')
    t.Start()
    
    results = []
    for opening in all_openings:
        opening_results = OpeningSetter.execute_all_functions(doc, opening, True)
        results.append(opening_results)
    
    if results == "OK":
        alert('All openings updated successfully.')
    else:
        alert('Completed with warnings. See the output window for more details.')
    
    t.Commit()

run()
