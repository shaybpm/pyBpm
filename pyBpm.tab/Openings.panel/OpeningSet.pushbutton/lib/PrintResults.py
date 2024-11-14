# -*- coding: utf-8 -*-


def print_results(output, results):
    output.print_html("<h1>Opening Set</h1>")
    output.print_html(
        '<div style="color:gray">Number of openings found: {}</div>'.format(
            len(results)
        )
    )

    statuses = [result["status"] for result in results]
    is_any_warning = "WARNING" in statuses
    if is_any_warning:
        num_of_openings_with_warnings = len(
            [status for status in statuses if status == "WARNING"]
        )
        output.print_html(
            '<h2 style="color:red">{} openings ended with warnings.</h2>'.format(
                num_of_openings_with_warnings
            )
        )
        message_warning_dict = {}
        for result in results:
            if result["status"] == "WARNING":
                for res in result["all_results"]:
                    if res["status"] == "WARNING":
                        message = res["message"]
                        if message in message_warning_dict:
                            message_warning_dict[message] += 1
                        else:
                            message_warning_dict[message] = 1
        message_warning_ul = "<ul>"
        for message, count in message_warning_dict.items():
            message_warning_ul += (
                '<li><span style="font-weight: bold;">{} {}:</span> {}</li>'.format(
                    count, "warnings" if count > 1 else "warning", message
                )
            )
        message_warning_ul += "</ul>"
        output.print_html(message_warning_ul)

        for result in results:
            if result["status"] == "WARNING":
                output.insert_divider()
                print(output.linkify(result["opening_id"]))
                for res in result["all_results"]:
                    if res["status"] == "WARNING":
                        output.print_html(
                            '<div style="color:red">{}</div>'.format(res["message"])
                        )
    else:
        output.print_html('<h2 style="color:green">End successfully.</h2>')


def print_full_results(output, results):
    output.print_html("<h1>Opening Set</h1>")
    output.print_html(
        '<div style="color:gray">Number of openings found: {}</div>'.format(
            len(results)
        )
    )

    is_any_warning = "WARNING" in [result["status"] for result in results]
    if is_any_warning:
        output.print_html('<h2 style="color:red">End with warnings.</h2>')

    for result in results:
        output.insert_divider()
        is_any_opening_warning = "WARNING" in [
            res["status"] for res in result["all_results"]
        ]
        if is_any_opening_warning:
            output.print_html(
                '<div style="color:red; text-decoration: underline">- Warning</div>'
            )
        else:
            output.print_html(
                '<div style="color:green; text-decoration: underline">- Ok</div>'
            )
        print(output.linkify(result["opening_id"]))
        for res in result["all_results"]:
            if res["status"] == "WARNING":
                output.print_html(
                    '<div style="color:red">{}</div>'.format(res["message"])
                )
            else:
                output.print_html(
                    '<div style="color:green">{}</div>'.format(res["message"])
                )
