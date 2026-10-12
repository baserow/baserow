class TeamDoesNotExist(Exception):
    """Raised when trying to get a team that does not exist."""


class TeamSubjectDoesNotExist(Exception):
    """Raised when trying to get a subject that does not exist."""


class TeamSubjectTypeUnsupported(Exception):
    """Raised when a subject is invited to a team, and we don't support its type."""


class TeamSubjectBadRequest(Exception):
    """Raised when a subject is created with no ID or email address."""


class RoleUnsupported(Exception):
    """Raised when an API consumer tries to assign a role we do not support."""


class SubjectNotExist(Exception):
    """Raised when trying to retrieve a subject that does not exist."""


class SubjectUnsupported(Exception):
    """Raised when trying to use an unsupported subject type."""


class ScopeNotExist(Exception):
    """Raised when trying to retrieve a scope that does not exist."""


class RoleNotExist(Exception):
    """Raised when trying to retrieve a role that does not exist."""


class ScopedInvitationDoesNotExist(Exception):
    """Raised when the requested scoped invitation does not exist."""
