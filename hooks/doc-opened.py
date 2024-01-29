try:
    from pyrevit import EXEC_PARAMS
    import os, sys

    sys.path.append(os.path.join("..", "lib"))
    from ServerUtils import ServerPermissions  # type: ignore

    doc = EXEC_PARAMS.event_args.Document

    server_permissions = ServerPermissions(doc)
    server_permissions.set_all_permissions()
except Exception as ex:
    from Config import get_env_mode  # type: ignore

    if get_env_mode() == "dev":
        print(ex)
