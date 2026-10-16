from uuid import UUID


class ChatRunAlreadyActive(Exception):
    """Raised when a chat already has a queued or running run."""

    def __init__(self, run_id: UUID) -> None:
        """
        :param run_id: The id of the chat's active run.
        """

        super().__init__(f"The chat already has the active run {run_id}.")
        self.run_id = run_id


class ChatRunLimitReached(Exception):
    """Raised when a user already has the maximum number of active runs."""


class ChatRunDoesNotExist(Exception):
    """Raised when a run can't be found."""
