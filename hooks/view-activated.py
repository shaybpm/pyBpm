# -*- coding: utf-8 -*-


def run():
    import os, sys

    lib_path = os.path.join("..", "lib")
    if lib_path not in sys.path:
        sys.path.append(lib_path)

    from pyrevit import EXEC_PARAMS
    from PyRevitUtils import ModelQualityAutoChecksToggleIcon
    from RevitUtils import handle_document_activated

    doc = EXEC_PARAMS.event_args.Document

    previous_active_view = EXEC_PARAMS.event_args.PreviousActiveView
    if not previous_active_view:
        return
    previous_active_document = previous_active_view.Document

    if previous_active_document.Title != doc.Title:
        handle_document_activated(doc)
    else:
        model_quality_auto_checks_toggle_icon = ModelQualityAutoChecksToggleIcon(doc)
        if not model_quality_auto_checks_toggle_icon.is_set_once():
            model_quality_auto_checks_toggle_icon.set_icon()


try:
    run()
except Exception as ex:
    from Config import get_env_mode

    if get_env_mode() == "dev":
        print(ex)
