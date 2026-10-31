from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_400_BAD_REQUEST


# The field API views can't know about the exceptions of plugins, so these are API
# exceptions that map themselves to a response.
class SemanticSearchNotAvailable(APIException):
    status_code = HTTP_400_BAD_REQUEST

    def __init__(self):
        super().__init__(
            {
                "error": "ERROR_SEMANTIC_SEARCH_NOT_AVAILABLE",
                "detail": "Semantic search requires pgvector and an embeddings "
                "service to be configured.",
            }
        )


class SemanticSearchNotSupported(APIException):
    status_code = HTTP_400_BAD_REQUEST

    def __init__(self, field_type: str):
        super().__init__(
            {
                "error": "ERROR_SEMANTIC_SEARCH_NOT_SUPPORTED",
                "detail": f"Semantic search is not supported for fields of type "
                f"{field_type}.",
            }
        )
