from typing import List, NamedTuple, Optional

from baserow.core.types import ScopeObject, Subject
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.models import Team


class AssignmentTuple(NamedTuple):
    subject_type_name: str
    subject_id: int
    original_role_uid: Optional[str]
    role_uid: Optional[str]
    scope_type_name: str
    scope_id: int


class NewRoleAssignment(NamedTuple):
    subject: Subject
    role: Role
    scope: ScopeObject


class EffectiveAccess(NamedTuple):
    """
    The role a user or an agent effectively holds on one scope, and where it comes
    from: `source_scope` is the scope, the given one or one above it, whose role
    applies, held by the subject themselves or, when `teams` isn't empty, through
    those teams.
    """

    subject: Subject
    role: Role
    source_scope: ScopeObject
    teams: List[Team]
