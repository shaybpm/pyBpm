def run():
    from pyrevit import EXEC_PARAMS
    import os, sys

    sys.path.append(os.path.join("..", "lib"))
    from ServerUtils import ServerPermissions  # type: ignore

    doc = EXEC_PARAMS.event_args.Document
    if not doc.IsModelInCloud:
        return

    server_permissions = ServerPermissions(doc)
    server_permissions.set_project_permissions()


try:
    run()
except Exception as ex:
    from Config import get_env_mode  # type: ignore

    if get_env_mode() == "dev":
        print(ex)
