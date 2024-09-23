import os
import clr
import json

clr.AddReferenceByPartialName("System")
from System.Collections.Generic import List

from Autodesk.Revit.DB import ElementId

from pyrevit import script
from pyrevit.coreutils import ribbon

from Config import root_path, server_url


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


class ModelQualityAutoChecksToggleIcon:
    def __init__(self, doc):
        self.doc = doc

        self.temp_file_path = script.get_instance_data_file(
            ModelQualityAutoChecksToggleIcon.__name__
        )

    def get_file_data(self):
        if not os.path.exists(self.temp_file_path):
            return {}
        with open(self.temp_file_path, "r") as f:
            return json.loads(f.read())

    def set_file_data(self, data):
        with open(self.temp_file_path, "w") as f:
            f.write(json.dumps(data))

    def set_set_once(self):
        data = self.get_file_data()
        if not data:
            data = {}
        if not data.get(self.doc.Title):
            data[self.doc.Title] = {}
        data[self.doc.Title]["set_once"] = True
        self.set_file_data(data)

    def is_set_once(self):
        data = self.get_file_data()
        if not data:
            return False
        model_data = data.get(self.doc.Title)
        if not model_data:
            return False
        return model_data.get("set_once", False)

    def set_icon(self):
        from ServerUtils import (
            is_model_quality_auto_checks_successful,
        )

        model_quality_auto_button_name = "ModelQualityAutoChecks"
        model_quality_auto_path = "{}\\pyBpm.tab\\BIM.panel\\{}.pushbutton\\".format(
            root_path, model_quality_auto_button_name
        )
        ui_button = ribbon.get_uibutton(model_quality_auto_button_name)
        if ui_button:
            if not is_model_quality_auto_checks_successful(self.doc, "A"):
                ui_button.set_icon(
                    model_quality_auto_path + "icon_failed.png",
                    icon_size=32,
                )
            else:
                ui_button.set_icon(
                    model_quality_auto_path + "icon.png",
                    icon_size=32,
                )
            self.set_set_once()


def open_pybpm_page(rel_target_html, rel_target_css, output=None):
    from HttpRequest import download_string

    target_html = server_url + rel_target_html
    target_css = server_url + rel_target_css

    if output:
        target_html += "?revit=true"

        html = download_string(target_html)
        # clear brake lines (because pyrevit output do it <br> tags)
        html = html.replace("\n", "")

        css_file = download_string(target_css)

        output.close_others()

        output.add_style(css_file)
        output.print_html(html)

        output.center()
        output.inject_script("window.scrollTo(0, 0);")
    else:
        start_process(target_html)
