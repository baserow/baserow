# TODO: Migrate callers to core.user.subject_types and core.subject.subject_types,
# then remove this compatibility module in a follow-up.
from baserow.core.subject.subject_types import AnonymousUserSubjectType
from baserow.core.user.subject_types import UserSubjectType

__all__ = ["AnonymousUserSubjectType", "UserSubjectType"]
