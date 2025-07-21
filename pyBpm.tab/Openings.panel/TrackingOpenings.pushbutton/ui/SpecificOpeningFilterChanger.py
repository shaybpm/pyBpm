from ExternalEventDataFile import ExternalEventDataFile
from EventHandlers import change_specific_openings_filter_event


class SpecificOpeningFilterChanger:
    def __init__(self, openings_with_new_approved_status):
        # deep copy of old_openings (only the relevant fields)
        self.openings_with_new_approved_status = openings_with_new_approved_status

    def get_openings(self):
        def op_filter(op):
            return op["approved"] != op["new_approved_status"] and (
                op["approved"] == "not approved"
                or op["new_approved_status"] == "not approved"
            )

        return [
            {
                "discipline": op["discipline"],
                "mark": op["mark"],
                "new_approved_status": op["new_approved_status"],
            }
            for op in self.openings_with_new_approved_status
            if op_filter(op)
        ]

    def change_filter(self, doc):
        try:
            openings = self.get_openings()
            if not openings:
                return

            ex_event_file = ExternalEventDataFile(doc)
            ex_event_file.set_key_value(
                "change_specific_openings_filter_data",
                openings,
            )
            change_specific_openings_filter_event.Raise()
        except Exception as e:
            print(e)
            raise e
