from ExternalEventDataFile import ExternalEventDataFile
from EventHandlers import change_specific_openings_filter_event


class SpecificOpeningFilterChanger:
    def __init__(self, old_openings, new_approved_status):
        # deep copy of old_openings (only the relevant fields)
        self.old_openings = [
            {
                "discipline": op["discipline"],
                "mark": op["mark"],
                "approved": op["approved"],
            }
            for op in old_openings
        ]
        self.new_approved_status = new_approved_status

    def get_openings(self):
        def op_filter(op):
            return op["approved"] != self.new_approved_status and (
                op["approved"] == "not approved"
                or self.new_approved_status == "not approved"
            )

        return [
            {"discipline": op["discipline"], "mark": op["mark"]}
            for op in self.old_openings
            if op_filter(op)
        ]

    def change_filter(self, doc):
        try:
            openings = self.get_openings()
            if not openings:
                return

            ex_event_file = ExternalEventDataFile(doc)
            change_specific_openings_filter_data = {
                "openings": openings,
                "new_approved_status": self.new_approved_status,
            }
            ex_event_file.set_key_value(
                "change_specific_openings_filter_data",
                change_specific_openings_filter_data,
            )
            change_specific_openings_filter_event.Raise()
        except Exception as e:
            print(e)
            raise e

    @staticmethod
    def get_changers_by_openings_with_new_approved_status(
        openings_with_new_approved_status,
    ):
        openings_by_new_approved_status = {}
        for opening in openings_with_new_approved_status:
            new_approved_status = opening["new_approved_status"]
            if new_approved_status not in openings_by_new_approved_status:
                openings_by_new_approved_status[new_approved_status] = []
            openings_by_new_approved_status[new_approved_status].append(opening)

        changers = []  # type: list[SpecificOpeningFilterChanger]
        for new_approved_status, openings in openings_by_new_approved_status.items():
            changers.append(SpecificOpeningFilterChanger(openings, new_approved_status))

        return changers
