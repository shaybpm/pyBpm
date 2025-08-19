# -*- coding: utf-8 -*-

import os
import json
from pyrevit.script import get_data_file

from Autodesk.Revit.DB import FilteredElementCollector, RevitLinkInstance
from RevitUtils import getElementName


class SRI_DialogResults:
    def __init__(self, doc):
        self.doc = doc
        self.data_file_name = get_data_file(
            doc.GetCloudModelPath().GetModelGUID().ToString(), "json", True
        )

        self.reservoir = []  # type: list[SRI_DialogResultsItem]
        self.sources = []  # type: list[SRI_DialogResultsItem]

        self.cb_func = None  # type: callable | None

        self.load_models()

    @property
    def all_items(self):
        return self.sources + self.reservoir

    def add_to_sources(self, item):  # type: (SRI_DialogResultsItem) -> None
        # Add item to sources and remove from reservoir
        if not item.is_valid():
            return
        if item not in self.sources:
            self.sources.append(item)
        if item in self.reservoir:
            self.reservoir.remove(item)

        if self.cb_func:
            self.cb_func(self.sources, self.reservoir)

    def remove_from_sources(self, item):  # type: (SRI_DialogResultsItem) -> None
        # Remove item from sources and add to reservoir
        if not item.is_valid():
            return
        if item in self.sources:
            self.sources.remove(item)
        if item not in self.reservoir:
            self.reservoir.append(item)

        if self.cb_func:
            self.cb_func(self.sources, self.reservoir)

    def clear_sources(self):
        # Clear all sources and move them to reservoir
        self.reservoir.extend(self.sources)
        self.sources = []

        if self.cb_func:
            self.cb_func(self.sources, self.reservoir)

    def clear_sources_and_add_one(self, item):  # type: (SRI_DialogResultsItem) -> None
        # Clear all sources and move them to reservoir
        if not item.is_valid():
            return
        self.reservoir.extend(self.sources)
        self.sources = []

        if item not in self.sources:
            self.sources.append(item)
        if item in self.reservoir:
            self.reservoir.remove(item)

        if self.cb_func:
            self.cb_func(self.sources, self.reservoir)

    def raise_source_priority(self, item):  # type: (SRI_DialogResultsItem) -> None
        # Raise the priority of the source item
        index = self.sources.index(item)
        if index <= 0:
            return
        self.sources[index], self.sources[index - 1] = (
            self.sources[index - 1],
            self.sources[index],
        )

        if self.cb_func:
            self.cb_func(self.sources, self.reservoir)

    def lower_source_priority(self, item):  # type: (SRI_DialogResultsItem) -> None
        # Lower the priority of the source item
        index = self.sources.index(item)
        if index < 0 or index >= len(self.sources) - 1:
            return
        self.sources[index], self.sources[index + 1] = (
            self.sources[index + 1],
            self.sources[index],
        )

        if self.cb_func:
            self.cb_func(self.sources, self.reservoir)

    def load_models(self):
        all_links = (
            FilteredElementCollector(self.doc).OfClass(RevitLinkInstance).ToElements()
        )

        source_link_ids = []
        if os.path.exists(self.data_file_name):
            with open(self.data_file_name, "r") as file:
                source_link_ids = json.load(file)

        for link in all_links:
            item = SRI_DialogResultsItem(link)
            if not item.is_valid():
                continue
            if item.link.Id.ToString() in source_link_ids:
                self.sources.append(item)
            else:
                self.reservoir.append(item)

        # sort sources by source_link_ids
        self.sources.sort(
            key=lambda x: (
                source_link_ids.index(x.link.Id.ToString())
                if x.link.Id.ToString() in source_link_ids
                else float("inf")
            )
        )

        if self.cb_func:
            self.cb_func(self.sources, self.reservoir)

    def save_models(self):
        source_link_ids = [item.link.Id.ToString() for item in self.sources]
        with open(self.data_file_name, "w") as file:
            json.dump(source_link_ids, file)


class SRI_DialogResultsItem:
    def __init__(self, link):
        self.link = link
        self.name = getElementName(link)  # type: str

    def is_valid(self):
        return self.link.GetLinkDocument() is not None

    def __eq__(self, value):
        if not isinstance(value, SRI_DialogResultsItem):
            return False
        return self.link.Id == value.link.Id
