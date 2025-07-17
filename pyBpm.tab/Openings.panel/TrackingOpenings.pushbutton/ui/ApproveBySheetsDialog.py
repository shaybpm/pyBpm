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


class ApproveBySheetsDialogResult:
    def __init__(self, openings, new_approved_status):
        # openings should be a list of dicts with: uniqueId, discipline, and mark
        # new_approved_status should be a list of dicts with: uniqueId and approved
        self.openings = openings
        self.new_approved_status = new_approved_status

class ApproveBySheetsDialog(Windows.Window):
    def __init__(self, data):
        wpf.LoadComponent(self, xaml_file)
        self.data = data
        self.result = None # type: ApproveBySheetsDialogResult | None

    def ok_btn_click(self, sender, e):
        # Logic for OK button click
        self.Close()

    def cancel_btn_click(self, sender, e):
        # Logic for Cancel button click
        self.Close()


# !
# TODO: Remove
# data_example = {
#     "_id": "687785e415fdb6be8fddedb0",
#     "projectGuid": "4fca2f38-b570-476f-a757-7527e16fabe6",
#     "modelGuid": "03fd4053-4c62-4994-b357-07c86a443a6b",
#     "sheets": [
#         {
#             "number": "400",
#             "uniqueId": "8f05895c-351f-4a55-8cc0-a664f75eca95-001552e1",
#             "title": "Sheet: 400 - Unnamed",
#             "name": "Unnamed",
#             "revisions": [
#                 {
#                     "revisionData": {
#                         "name": "Seq. 11 - פתחים",
#                         "description": "פתחים",
#                         "number": "8",
#                         "sequenceNumber": 11,
#                         "numberingSequenceId": "1515885",
#                         "uniqueId": "96f56a0d-55ea-417c-a4d9-c6dbd45f510c-001889c1",
#                         "date": "16-07-2025",
#                         "issued": False,
#                         "issuesBy": "",
#                         "issuedTo": "",
#                     },
#                     "openings": [
#                         {
#                             "uniqueId": "08c2fc0d-5eb8-4ab7-a537-505aadb0245f-007c48e0",
#                             "mark": "2",
#                             "name": "Round Face Opening",
#                             "discipline": "A",
#                             "approved": None,
#                         },
#                         {
#                             "uniqueId": "08c2fc0d-5eb8-4ab7-a537-505aadb0245f-007c4965",
#                             "mark": "3",
#                             "name": "Round Face Opening",
#                             "discipline": "A",
#                             "approved": None,
#                         },
#                         {
#                             "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e7d16",
#                             "mark": "3",
#                             "name": "Rectangular Face Opening",
#                             "discipline": "H",
#                             "approved": "not treated",
#                         },
#                         {
#                             "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e7efb",
#                             "mark": "4",
#                             "name": "Rectangular Face Opening",
#                             "discipline": "H",
#                             "approved": "not approved",
#                         },
#                         {
#                             "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e7fea",
#                             "mark": "5",
#                             "name": "Rectangular Face Opening",
#                             "discipline": "H",
#                             "approved": "conditionally approved",
#                         },
#                         {
#                             "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e8025",
#                             "mark": "6",
#                             "name": "Rectangular Face Opening",
#                             "discipline": "H",
#                             "approved": "conditionally approved",
#                         },
#                         {
#                             "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e80b4",
#                             "mark": "7",
#                             "name": "Round Face Opening",
#                             "discipline": "H",
#                             "approved": "approved",
#                         },
#                         {
#                             "uniqueId": "b575d908-7732-4ddc-9d1d-d6604d43b521-000e80df",
#                             "mark": "8",
#                             "name": "Round Face Opening",
#                             "discipline": "H",
#                             "approved": "not approved",
#                         },
#                         {
#                             "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e8221",
#                             "mark": "9",
#                             "name": "Rectangular Face Opening",
#                             "discipline": "H",
#                             "approved": "not approved",
#                         },
#                         {
#                             "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e8264",
#                             "mark": "10",
#                             "name": "Rectangular Face Opening",
#                             "discipline": "H",
#                             "approved": "not treated",
#                         },
#                         {
#                             "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e82b2",
#                             "mark": "11",
#                             "name": "Rectangular Face Opening",
#                             "discipline": "H",
#                             "approved": "not treated",
#                         },
#                         {
#                             "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e82ed",
#                             "mark": "12",
#                             "name": "Round Face Opening",
#                             "discipline": "H",
#                             "approved": "not treated",
#                         },
#                         {
#                             "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e830f",
#                             "mark": "13",
#                             "name": "Round Face Opening",
#                             "discipline": "H",
#                             "approved": "not treated",
#                         },
#                         {
#                             "uniqueId": "223c46ef-a2e5-402c-9b3a-6ac087bd024a-000e832f",
#                             "mark": "14",
#                             "name": "Round Face Opening",
#                             "discipline": "H",
#                             "approved": "not treated",
#                         },
#                     ],
#                 }
#             ],
#         }
#     ],
#     "__v": 0,
# }
