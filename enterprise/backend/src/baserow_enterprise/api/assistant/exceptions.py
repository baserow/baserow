from uuid import UUID

from rest_framework.exceptions import APIException

from baserow.api.chat_runs.errors import ERROR_CHAT_RUN_IN_PROGRESS


class ChatRunInProgressAPIException(APIException):
    """The chat is still answering a message; the client can follow its run."""

    def __init__(self, run_id: UUID) -> None:
        """
        :param run_id: The id of the chat's active run.
        """

        error, status_code, detail = ERROR_CHAT_RUN_IN_PROGRESS
        super().__init__({"error": error, "detail": detail, "run_id": str(run_id)})
        self.status_code = status_code
