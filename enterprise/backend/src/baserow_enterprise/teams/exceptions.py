from typing import Any, Dict, List


class TeamDoesNotExist(Exception):
    """Raised when trying to get a team that does not exist."""

    def __init__(self, team=None, *args, **kwargs):
        super().__init__("The team does not exist.", *args, **kwargs)


class TeamNameNotUnique(Exception):
    """Raised when trying to create/update a team and the name is in use in the group"""

    def __init__(self, name=None, *args, **kwargs):
        if name:
            super().__init__(f"Team {name} is already in use.", *args, **kwargs)
        else:
            super().__init__("The team name is already in use.", *args, **kwargs)


class TeamSubjectDoesNotExist(Exception):
    """Raised when trying to get a subject that does not exist."""

    def __init__(self, actor_id=None, *args, **kwargs):
        if actor_id:
            super().__init__(f"Actor {actor_id} does not exist.", *args, **kwargs)
        else:
            super().__init__(
                "The specific team subject actor does not exist.", *args, **kwargs
            )


class TeamSubjectBulkDoesNotExist(Exception):
    """Raised when trying to get a subject that does not exist."""

    def __init__(self, missing_subjects: List[Dict[str, Any]], *args, **kwargs):
        self.missing_subjects = missing_subjects


class TeamSubjectBadRequest(Exception):
    """Raised when a subject is created with no ID or email address."""

    def __init__(self, *args, **kwargs):
        super().__init__("An ID or email address is required.", *args, **kwargs)


class TeamSubjectTypeUnsupported(Exception):
    """Raised when a subject is invited to a team, and we don't support its type."""

    def __init__(self, subject_type: str, *args, **kwargs):
        if subject_type:
            super().__init__(
                f"Type {subject_type} is not a supported team subject type.",
                *args,
                **kwargs,
            )
        else:
            super().__init__("The subject type is not supported.", *args, **kwargs)


class TeamSubjectNotInGroup(Exception):
    """Raised when a subject is created, and they don't belong to the team's group."""

    def __init__(self, *args, **kwargs):
        super().__init__(
            "This subject does not belong to the team's group.", *args, **kwargs
        )


class TeamInvitationDoesNotExist(Exception):
    """Raised when trying to get an invitation to a team that does not exist."""
