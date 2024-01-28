try:
    from pyrevit import EXEC_PARAMS
    import os, sys

    root_path = __file__[: __file__.rindex(".extension") + len(".extension")]
    sys.path.append(os.path.join(root_path, "lib"))
    from Config import ServerPermissions  # type: ignore

    doc = EXEC_PARAMS.event_args.Document

    server_permissions = ServerPermissions(doc)
    server_permissions.set_all_permissions()
except Exception as ex:
    from Config import get_env_mode  # type: ignore

    if get_env_mode() == "dev":
        print(ex)
