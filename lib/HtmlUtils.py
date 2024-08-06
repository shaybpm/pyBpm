# -*- coding: utf-8 -*-


class HtmlUtils:
    def __init__(self):
        self._html = ""

    def add_html(self, html):
        self._html += html

    def add_break(self):
        self.add_html("<br>")

    def get_html(self):
        return self._html
