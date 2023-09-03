try:
	import clr
	clr.AddReference('RevitAPI')

	from Autodesk.Revit.DB import Transaction

	# ------------------------------------------------------------
	from pyrevit import EXEC_PARAMS
	doc = EXEC_PARAMS.event_args.Document
	# ------------------------------------------------------------

	# Run the "Opening setter" script without printing anything to the console and without showing any dialogs.
	import sys, os
	sys.path.append(os.path.join(os.path.dirname(__file__), "..", "pyBpmExternal.tab", "Openings.panel", "OpeningSetter.pushbutton", "lib"))
	import OpeningSetter

	all_openings = OpeningSetter.get_all_openings(doc)
	t = Transaction(doc, 'BPM | Opening Update')
	t.Start()
	for opening in all_openings:
		results = OpeningSetter.execute_all_functions(doc, opening)
	t.Commit()

except Exception as e:
	# TODO: If it's development mode, show the error message.
	if "Software_Development\RevitDevelopment\PyRevitBpm" in __file__:
		print(e)
except:
	pass
