import os
import clr

clr.AddReferenceByPartialName("System")
from System.Collections.Generic import List

from Autodesk.Revit.DB import ElementId

from pyrevit import script


class TempElementStorage:
    def __init__(self, file_id):
        self.file_path = script.get_instance_data_file(file_id)

    def is_file_exists(self):
        return os.path.isfile(self.file_path)

    def get_data(self):
        if not self.is_file_exists():
            return []
        with open(self.file_path, "r") as f:
            data = f.read()
            if not data:
                return []
            data = data.split(",")
            return data

    def add_element(self, element_id):
        id_val_str = str(element_id.IntegerValue)
        data = self.get_data()
        if id_val_str in data:
            return
        data.append(id_val_str)
        with open(self.file_path, "w") as f:
            f.write(",".join(data))

    def add_elements(self, element_ids):
        data = self.get_data()
        for element_id in element_ids:
            id_val_str = str(element_id.IntegerValue)
            if id_val_str in data:
                continue
            data.append(id_val_str)
        with open(self.file_path, "w") as f:
            f.write(",".join(data))

    def remove_element(self, element_id):
        data = self.get_data()
        if str(element_id.IntegerValue) not in data:
            return
        data.remove(str(element_id.IntegerValue))
        with open(self.file_path, "w") as f:
            f.write(",".join(data))

    def remove_elements(self, element_ids):
        data = self.get_data()
        for element_id in element_ids:
            if str(element_id.IntegerValue) not in data:
                continue
            data.remove(str(element_id.IntegerValue))
        with open(self.file_path, "w") as f:
            f.write(",".join(data))

    def get_element_ids(self):
        data = self.get_data()
        return List[ElementId]([ElementId(int(x)) for x in data])


def print_table(output, columns, table_data):
    """Prints table to output."""
    output_str = '<table style="text-align: center;">'
    output_str += "<tr>"
    for column in columns:
        output_str += "<th>{}</th>".format(column)
    output_str += "</tr>"
    for row in table_data:
        output_str += "<tr>"
        for cell in row:
            output_str += "<td>{}</td>".format(cell)
        output_str += "</tr>"
    output_str += "</table>"
    output.print_html(output_str)


def start_process(path):
    from System.Diagnostics.Process import Start  # type: ignore

    Start(path)
