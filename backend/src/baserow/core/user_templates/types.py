from typing import List, TypedDict


class TemplateMetadata(TypedDict, total=False):
    """
    The private metadata of a template revision, only shown to its owner. It's
    read and written through `UserTemplateHandler` only.
    """

    # The workspace the applications of the revision were copied from.
    source_workspace_id: int
    # The ids of the applications the revision was copied from.
    source_application_ids: List[int]
