import typing

ROW_IMPORT_VALIDATION = "row-import-validation"
ROW_IMPORT_CREATION = "row-import-creation"


class DataImportDict(typing.TypedDict):
    data: list[list[typing.Any]]
    configuration: None | dict[str, typing.Any]
