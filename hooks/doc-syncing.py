# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import Transaction

from pyrevit import EXEC_PARAMS

from PyRevitUtils import TempElementStorage  # type: ignore
from Config import OPENING_ST_TEMP_FILE_ID  # type: ignore

import sys, os

sys.path.append(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "pyBpm.tab",
        "Openings.panel",
        "OpeningSet.pushbutton",
        "lib",
    )
)
from OpeningSet import Preprocessor, execute_all_functions  # type: ignore

doc = EXEC_PARAMS.event_args.Document

temp_storage = TempElementStorage(OPENING_ST_TEMP_FILE_ID)
opening_ids = temp_storage.get_element_ids()

if len(opening_ids) > 0:
    t = Transaction(doc, "BPM | Opening Set")
    t.Start()

    failOpt = t.GetFailureHandlingOptions()
    preprocessor = Preprocessor()
    failOpt.SetFailuresPreprocessor(preprocessor)
    t.SetFailureHandlingOptions(failOpt)

    for opening_id in opening_ids:
        opening = doc.GetElement(opening_id)
        if not opening:
            print(
                "Opening not found"
            )  # TODO: Remove after testing and before margin branch. and wrap with try/except all this file
            temp_storage.remove_element(opening_id)
            continue
        execute_all_functions(doc, opening)

    t.Commit()
