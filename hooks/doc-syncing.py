import clr
clr.AddReference('RevitAPI')
clr.AddReferenceByPartialName('PresentationCore')
clr.AddReferenceByPartialName('AdWindows')
clr.AddReferenceByPartialName("PresentationFramework")
clr.AddReferenceByPartialName('System')
clr.AddReferenceByPartialName('System.Windows.Forms')

from Autodesk.Revit.DB import Transaction

max_elements = 5
gdict = globals()
uiapp = __revit__
uidoc = uiapp.ActiveUIDocument
if uidoc:
    doc = uiapp.ActiveUIDocument.Document

# ------------------------------------------------------------

# Run the "Opening setter" script without printing anything to the console and without showing any dialogs.
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "pyBpmExternal.tab", "Openings.panel", "OpeningSetter.pushbutton", "lib"))
import OpeningSetter

try:
	all_openings = OpeningSetter.get_all_openings()
	t = Transaction(doc, 'BPM | Opening Update')
	t.Start()
	for opening in all_openings:
		results = OpeningSetter.execute_all_functions(opening, False)
	t.Commit()
except:
	pass
