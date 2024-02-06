from Config import get_env_mode  # type: ignore

try:
    if get_env_mode() == "prod":
        import os, sys
        import sys, os

        sys.path.append(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "pyBpm.tab",
                "BPM.panel",
                "Update.smartbutton",
                "lib",
            )
        )
        import Update  # type: ignore

        sys.path.append(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "lib",
            )
        )
        from Config import server_url, get_current_version  # type: ignore
        import HttpRequest  # type: ignore

        version_update_required_dict = HttpRequest.get(
            server_url + "api/info/v-update-required"
        )
        if version_update_required_dict:
            version_update_required = version_update_required_dict["version"]
            version_update_required_list = version_update_required.split(".")
            version_update_required_list = [
                int(x) for x in version_update_required_list
            ]

            current_version = get_current_version()
            current_version_list = current_version.split(".")
            current_version_list = [int(x) for x in current_version_list]

            if (
                (version_update_required_list[0] > current_version_list[0])
                or (
                    version_update_required_list[0] == current_version_list[0]
                    and version_update_required_list[1] > current_version_list[1]
                )
                or (
                    version_update_required_list[0] == current_version_list[0]
                    and version_update_required_list[1] == current_version_list[1]
                    and version_update_required_list[2] > current_version_list[2]
                )
            ):
                Update.run(do_not_print=True)

except Exception as ex:
    if get_env_mode() == "dev":
        print(ex)
