# -*- coding: utf-8 -*-


def run():
    from pyrevit import EXEC_PARAMS
    import os, sys

    lib_path = os.path.join("..", "lib")
    if lib_path not in sys.path:
        sys.path.append(lib_path)

    from RevitUtils import handle_document_activated

    doc = EXEC_PARAMS.event_args.Document

    handle_document_activated(doc)


try:
    run()
except Exception as ex:
    from Config import get_env_mode

    if get_env_mode() == "dev":
        print(ex)
