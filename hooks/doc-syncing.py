import clr
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import Transaction

# ------------------------------------------------------------
from pyrevit import EXEC_PARAMS
doc = EXEC_PARAMS.event_args.Document
# ------------------------------------------------------------

# Run the "Opening setter" script without printing anything to the console and without showing any dialogs.
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "pyBpmExternal.tab", "Openings.panel", "OpeningSetter.pushbutton", "lib"))
import OpeningSetter

try:
	all_openings = OpeningSetter.get_all_openings(doc)
	t = Transaction(doc, 'BPM | Opening Update')
	t.Start()
	for opening in all_openings:
		results = OpeningSetter.execute_all_functions(doc, opening, False)
	t.Commit()
except Exception as e:
	print("ERROR: {}".format(e))
