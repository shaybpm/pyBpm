# -*- coding: utf-8 -*-

import clr

clr.AddReference("System.Windows.Forms")
try:
    clr.AddReference("IronPython.Wpf")
except:
    pass

from System import Windows
from pyrevit.framework import wpf
import os

xaml_file = os.path.join(os.path.dirname(__file__), "ApproveBySheetsDialogUi.xaml")


class ApproveBySheetsDialog(Windows.Window):
    def __init__(self, data):
        wpf.LoadComponent(self, xaml_file)
        self.doc = data

    def ok_btn_click(self, sender, e):
        # Logic for OK button click
        self.Close()

    def cancel_btn_click(self, sender, e):
        # Logic for Cancel button click
        self.Close()

# !
# TODO: Remove
# data_example = [
#     {
#         "_id": "687785e415fdb6be8fddedb0",
#         "__v": 0,
#         "projectGuid": "4fca2f38-b570-476f-a757-7527e16fabe6",
#         "sheets": [
#             {
#                 "number": "400",
#                 "revisions": [
#                     {
#                         "revisionData": {
#                             "description": "\u05f3\u20aa\u05f3\xd7\u05f3\u2014\u05f3\u2122\u05f3\x9d",
#                             "number": "8",
#                             "name": "Seq. 11 - \u05f3\u20aa\u05f3\xd7\u05f3\u2014\u05f3\u2122\u05f3\x9d",
#                             "numberingSequenceId": "1515885",
#                             "sequenceNumber": 11,
#                             "uniqueId": "96f56a0d-55ea-417c-a4d9-c6dbd45f510c-001889c1",
#                             "date": "16-07-2025",
#                             "issued": False,
#                             "issuedTo": "",
#                             "issuesBy": "",
#                         },
#                         "openings": [
#                             {
#                                 "uniqueId": "08c2fc0d-5eb8-4ab7-a537-505aadb0245f-007c48e0",
#                                 "discipline": "A",
#                                 "name": "Round Face Opening",
#                                 "mark": "2",
#                             },
#                             {
#                                 "uniqueId": "08c2fc0d-5eb8-4ab7-a537-505aadb0245f-007c4965",
#                                 "discipline": "A",
#                                 "name": "Round Face Opening",
#                                 "mark": "3",
#                             },
#                             {
#                                 "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e7d16",
#                                 "discipline": "H",
#                                 "name": "Rectangular Face Opening",
#                                 "mark": "3",
#                             },
#                             {
#                                 "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e7efb",
#                                 "discipline": "H",
#                                 "name": "Rectangular Face Opening",
#                                 "mark": "4",
#                             },
#                             {
#                                 "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e7fea",
#                                 "discipline": "H",
#                                 "name": "Rectangular Face Opening",
#                                 "mark": "5",
#                             },
#                             {
#                                 "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e8025",
#                                 "discipline": "H",
#                                 "name": "Rectangular Face Opening",
#                                 "mark": "6",
#                             },
#                             {
#                                 "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e80b4",
#                                 "discipline": "H",
#                                 "name": "Round Face Opening",
#                                 "mark": "7",
#                             },
#                             {
#                                 "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e80df",
#                                 "discipline": "H",
#                                 "name": "Round Face Opening",
#                                 "mark": "8",
#                             },
#                             {
#                                 "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e8221",
#                                 "discipline": "H",
#                                 "name": "Rectangular Face Opening",
#                                 "mark": "9",
#                             },
#                             {
#                                 "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e8264",
#                                 "discipline": "H",
#                                 "name": "Rectangular Face Opening",
#                                 "mark": "10",
#                             },
#                             {
#                                 "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e82b2",
#                                 "discipline": "H",
#                                 "name": "Rectangular Face Opening",
#                                 "mark": "11",
#                             },
#                             {
#                                 "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e82ed",
#                                 "discipline": "H",
#                                 "name": "Round Face Opening",
#                                 "mark": "12",
#                             },
#                             {
#                                 "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e830f",
#                                 "discipline": "H",
#                                 "name": "Round Face Opening",
#                                 "mark": "13",
#                             },
#                             {
#                                 "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e832f",
#                                 "discipline": "H",
#                                 "name": "Round Face Opening",
#                                 "mark": "14",
#                             },
#                         ],
#                     }
#                 ],
#                 "name": "Unnamed",
#                 "title": "Sheet: 400 - Unnamed",
#                 "uniqueId": "8f05895c-351f-4a55-8cc0-a664f75eca95-001552e1",
#             }
#         ],
#         "modelGuid": "03fd4053-4c62-4994-b357-07c86a443a6b",
#     }
# ]
