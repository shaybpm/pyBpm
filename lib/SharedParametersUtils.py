from Autodesk.Revit.DB import (
    TransactionGroup,
    Transaction,
)
from System import Guid
from Config import shared_parameters_path

from RevitUtils import getRevitVersion


class SharedParameterManager:
    def __init__(self, app, doc):
        self.doc = doc
        self.app = app
        self.current_sp_file_name = self.app.SharedParametersFilename

    def __enter__(self):
        self.app.SharedParametersFilename = shared_parameters_path
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.app.SharedParametersFilename = self.current_sp_file_name
        return False  # re-raise any exception that occurred

    def get_shared_parameter_by_guid(self, guid):
        sp_file = self.app.OpenSharedParameterFile()
        for group in sp_file.Groups:
            for p_def in group.Definitions:
                if p_def.GUID.ToString() == guid:
                    return p_def
        return None

    def get_default_p_group_or_f_type_id(self):
        revit_version = getRevitVersion(self.doc)
        if revit_version >= 2024:
            from Autodesk.Revit.DB import GroupTypeId

            return GroupTypeId.Data
        else:
            from Autodesk.Revit.DB import BuiltInParameterGroup

            return BuiltInParameterGroup.PG_DATA

    def add_shared_parameter_to_categories(
        self, sp_guid, categories, p_group_or_f_type_id=None, type_binding=False
    ):
        if isinstance(sp_guid, Guid):
            sp_guid = sp_guid.ToString()

        if p_group_or_f_type_id is None:
            p_group_or_f_type_id = self.get_default_p_group_or_f_type_id()

        sp_def = self.get_shared_parameter_by_guid(sp_guid)
        if not sp_def:
            raise ValueError("Shared parameter with GUID {} not found.".format(sp_guid))

        cat_set = self.app.Create.NewCategorySet()
        for category in categories:
            cat_set.Insert(category)

        binding = (
            self.app.Create.NewInstanceBinding(cat_set)
            if not type_binding
            else self.app.Create.NewTypeBinding(cat_set)
        )

        transaction = Transaction(self.doc, "pyBpm | Add Shared Parameter")
        transaction.Start()
        self.doc.ParameterBindings.Insert(sp_def, binding, p_group_or_f_type_id)
        transaction.Commit()

    def add_shared_parameters_to_categories(
        self, sp_guids, categories, p_group_or_f_type_id=None, type_binding=False
    ):
        if p_group_or_f_type_id is None:
            p_group_or_f_type_id = self.get_default_p_group_or_f_type_id()

        transaction_group = TransactionGroup(self.doc, "pyBpm | Add Shared Parameters")
        transaction_group.Start()
        for sp_guid in sp_guids:
            self.add_shared_parameter_to_categories(
                sp_guid, categories, p_group_or_f_type_id, type_binding
            )
        transaction_group.Assimilate()


class PyBpmSharedParameter:
    def __init__(self, guid, name):
        self.guid = Guid(guid) if isinstance(guid, str) else guid
        self.name = name


class PyBpmSharedParameters:
    def __init__(self):
        self.BPM_FM_ID = PyBpmSharedParameter(
            guid="0705aa06-ef11-489f-968f-a86d1d9b307a",
            name="BPM_FM_ID",
        )
        self.BPM_Room_Level = PyBpmSharedParameter(
            guid="9c8ae834-336c-4561-bfc6-bb28219a5796",
            name="BPM_Room_Level",
        )
        self.BPM_FM_Mark = PyBpmSharedParameter(
            guid="0d2ebd4c-c937-41eb-9699-ba29a0ed5830",
            name="BPM_FM_Mark",
        )
        self.BPM_FM_SubType = PyBpmSharedParameter(
            guid="7a2aab5d-cead-448f-a2e5-1be8fe8815e3", name="BPM_FM_SubType"
        )
        self.BPM_FM_Type = PyBpmSharedParameter(
            guid="fac4029d-f610-42d8-a3cd-cf0d17eec790", name="BPM_FM_Type"
        )
        self.BPM_Room_Num = PyBpmSharedParameter(
            guid="0325979e-3b57-4594-8858-a68c61f07034", name="BPM_Room_Num"
        )
        self.BPM_Link_Source = PyBpmSharedParameter(
            guid="9fdb75df-6d5d-411b-ab0a-8688067c9619", name="BPM_Link_Source"
        )
        self.BPM_Room_Name = PyBpmSharedParameter(
            guid="8da413fc-0116-4f9b-b355-2d014a23d4f3", name="BPM_Room_Name"
        )

    def get_parameter_by_name(self, name):  # type: (str) -> PyBpmSharedParameter | None
        return getattr(self, name, None)

    def to_list(self):
        return [
            self.BPM_FM_ID,
            self.BPM_Room_Level,
            self.BPM_FM_Mark,
            self.BPM_FM_SubType,
            self.BPM_FM_Type,
            self.BPM_Room_Num,
            self.BPM_Link_Source,
            self.BPM_Room_Name,
        ]

    @staticmethod
    def to_list_static():
        instance = PyBpmSharedParameters()
        return instance.to_list()
