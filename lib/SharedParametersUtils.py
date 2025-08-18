from Autodesk.Revit.DB import (
    BuiltInParameterGroup,
    Transaction,
)

from Config import shared_parameters_path


class SharedParameterManager:
    def __init__(self, doc):
        self.doc = doc
        self.app = __revit__.Application  # type: ignore
        self.current_sp_file_name = self.app.SharedParametersFilename

        self.transaction = None

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

    def add_shared_parameter_to_categories(
        self, sp_guid, categories, parameter_group=BuiltInParameterGroup.PG_TEXT
    ):
        sp_def = self.get_shared_parameter_by_guid(sp_guid)
        if not sp_def:
            raise ValueError("Shared parameter with GUID {} not found.".format(sp_guid))
        cat_set = self.app.Create.NewCategorySet()
        for category in categories:
            cat_set.Insert(category)

        new_instance_binding = self.app.Create.NewInstanceBinding(cat_set)

        if self.transaction is None:
            self.transaction = Transaction(self.doc, "pyBpm | Add Shared Parameter")
        if not self.transaction.HasStarted():
            self.transaction.Start()

        self.doc.ParameterBindings.Insert(sp_def, new_instance_binding, parameter_group)

        if self.transaction.HasStarted():
            self.transaction.Commit()
            self.transaction = None

    def add_shared_parameters_to_categories(
        self, sp_guids, categories, parameter_group=BuiltInParameterGroup.PG_TEXT
    ):
        self.transaction = Transaction(self.doc, "pyBpm | Add Shared Parameters")
        self.transaction.Start()
        for sp_guid in sp_guids:
            self.add_shared_parameter_to_categories(
                sp_guid, categories, parameter_group
            )
        self.transaction.Commit()
        self.transaction = None


class PyBpmSharedParameter:
    def __init__(self, guid):
        self.guid = guid


class PyBpmSharedParameters:
    def __init__(self):
        self.BPM_FM_ID = PyBpmSharedParameter("0705aa06-ef11-489f-968f-a86d1d9b307a")
        self.BPM_FM_Mark = PyBpmSharedParameter("0d2ebd4c-c937-41eb-9699-ba29a0ed5830")
        self.BPM_FM_SubType = PyBpmSharedParameter(
            "7a2aab5d-cead-448f-a2e5-1be8fe8815e3"
        )
        self.BPM_FM_Type = PyBpmSharedParameter("fac4029d-f610-42d8-a3cd-cf0d17eec790")
        self.BPM_Room_Num = PyBpmSharedParameter("0325979e-3b57-4594-8858-a68c61f07034")
        self.BPM_Level = PyBpmSharedParameter("6fb986db-df6b-44a0-8fb3-2472866af0d5")
        self.BPM_Room_Name = PyBpmSharedParameter(
            "8da413fc-0116-4f9b-b355-2d014a23d4f3"
        )

    def to_list(self):
        return [
            self.BPM_FM_ID,
            self.BPM_FM_Mark,
            self.BPM_FM_SubType,
            self.BPM_FM_Type,
            self.BPM_Room_Num,
            self.BPM_Level,
            self.BPM_Room_Name,
        ]

    @staticmethod
    def to_list_static():
        instance = PyBpmSharedParameters()
        return instance.to_list()
