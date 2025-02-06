import dataclasses


@dataclasses.dataclass
class AirtableImportConfig:
    skip_files: bool = False
    """
    Indicates whether the files should not be downloaded and included in the
    config. This can significantly improve the improvements.
    """
