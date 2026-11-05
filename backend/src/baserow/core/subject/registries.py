import abc
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q, QuerySet

from rest_framework.serializers import Serializer

from baserow.core.exceptions import SubjectTypeNotExist
from baserow.core.registry import (
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.types import Subject

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Workspace


class SubjectType(abc.ABC, Instance, ModelInstanceMixin):
    """
    This type describes a subject that exists in Baserow. A subject is anything that
    can execute an operation.
    """

    # Permission actors opt in explicitly; teams and anonymous actors have no
    # persistent row identity merely because they are registered subject types.
    supports_persistent_subjects = False
    persistent_subject_disabled_message = (
        "Field references are disabled for this subject type."
    )

    def register_lifecycle_signals(self):
        """Connect type-owned identity lifecycle receivers at application startup."""

    def retain_persistent_subject(self, subject_id, *, using="default"):
        """Keep attribution after its actor or link disappears."""
        from baserow.core.models import Subject

        if subject_id is not None:
            Subject.objects.using(using).filter(pk=subject_id, type=self.type).update(
                state="retained"
            )

    def synchronize_persistent_subject(self, actor, *, using="default"):
        """Synchronize attribution after saving an actor, within its transaction."""
        raise NotImplementedError()

    def persistent_subject_references_enabled(self):
        """Whether new field references to this type can currently be written."""
        return self.supports_persistent_subjects

    def get_persistent_subject_workspace_filter(self, workspace_id, *, selectable=True):
        """Return a Q over core.Subject, suitable for composing one batched query."""
        return Q(pk__in=[])

    def has_invalid_persistent_subjects(self):
        """Check live actor links and cached identity values before activation."""
        raise NotImplementedError()

    def get_legacy_persistent_subject_uid(self, value):
        """Recognize legacy portable values owned by this type, if any."""
        return None

    def export_persistent_subject(self, subject):
        """Export retained identity metadata without resolving the concrete actor."""
        return {
            "version": 1,
            "type": self.type,
            "uid": subject.uid,
            "name": subject.name,
        }

    def import_persistent_subject(self, identity, workspace_id, cache):
        """Match eligible identities or retain metadata without creating an actor.

        Legacy values only match existing workspace identities. The operation cache
        shares eligibility, activation and retained identities across all references.
        """
        from baserow.core.models import Subject as PersistentSubject
        from baserow.core.subject.handler import SubjectHandler

        if not self.supports_persistent_subjects:
            raise ValueError("Unsupported exported Subject identity")
        cache = cache.setdefault("subject_identity_mapping", {})
        legacy = isinstance(identity, str)
        if legacy:
            uid = self.get_legacy_persistent_subject_uid(identity)
            if uid is None:
                return None
        else:
            if (
                not isinstance(identity, dict)
                or identity.get("version") != 1
                or identity.get("type") != self.type
            ):
                raise ValueError("Unsupported exported Subject identity")
            uid = identity.get("uid")
            if not isinstance(uid, str) or not isinstance(identity.get("name"), str):
                raise ValueError("Invalid exported Subject identity")
            if not SubjectHandler().persistent_subject_references_enabled(self, cache):
                raise ValidationError(self.persistent_subject_disabled_message)
        key = ("identity_import", workspace_id)
        if key not in cache:
            cache[key] = {
                (s.type, s.uid): s
                for s in SubjectHandler().eligible_subjects(workspace_id)
            }
        match = cache[key].get((self.type, uid))
        if match is not None or legacy:
            return match
        retained_key = ("retained_identity", json.dumps(identity, sort_keys=True))
        if retained_key not in cache:
            cache[retained_key] = PersistentSubject.objects.create(
                id=SubjectHandler().allocate_subject_id(),
                type=self.type,
                uid=uid,
                name=identity["name"],
                state="retained",
            )
        return cache[retained_key]

    def get_persistent_subject_export_value(self, subject, *, include_name=True):
        """Format retained attribution without resolving a potentially deleted actor."""
        return f"{subject.name} <{subject.uid}>"

    def get_persistent_subject(self, actor, *, for_write=False):
        """Resolve live attribution, enforcing type capabilities and write activation."""
        if not self.supports_persistent_subjects or not getattr(actor, "pk", None):
            return None
        try:
            subject = self._get_persistent_subject(actor)
        except ObjectDoesNotExist:
            return None
        if subject is None or subject.state != "live":
            return None
        if for_write and not self.persistent_subject_references_enabled():
            return None
        return subject

    def _get_persistent_subject(self, actor):
        """Look up this concrete actor's retained identity without granting access."""
        return None

    def resolve_persistent_subject(self, subject):
        """Return a live actor, or None when execution is unavailable."""
        return None

    # Interactive users can persist undoable actions and emit product analytics.
    is_interactive_user = False
    display_name_field: Optional[str] = None
    lookup_fields = ("id", "pk")
    options_list_operation_type: Optional[str] = None

    def supports_lookup_field(self, field_name: str) -> bool:
        """Return whether this subject type supports lookup by the given field."""

        return field_name in self.lookup_fields

    # Types opting in own workspace role persistence outside RoleAssignment and
    # must implement get_workspace_subjects, get_workspace_role_uids, and
    # set_workspace_role_uid. Other types keep using RoleAssignment records.
    has_direct_workspace_roles: bool = False

    def track_usage(self, subject: Subject) -> None:
        """Record usage when a subject dispatches a service through an integration."""

        pass

    def get_workspace_subjects(self, workspace: "Workspace", include_trash=False):
        """Return the subjects whose direct roles belong to a workspace.

        :param workspace: The workspace that the returned subjects must belong to.
        :param include_trash: Whether trashed subjects or memberships can be returned.
        :return: The workspace subjects to include in direct-role listings.
        """
        raise NotImplementedError()

    def set_workspace_role_uid(
        self,
        subject: Subject,
        workspace: "Workspace",
        role_uid: str,
        send_signals: bool = True,
    ):
        """Persist a subject's direct role in a workspace.

        :param subject: The subject whose direct role must be changed.
        :param workspace: The workspace in which to change the role.
        :param role_uid: The UID of the direct role to persist.
        :param send_signals: Whether to emit the subject and permission update signals.
        :return: The implementation-specific result of persisting the role.
        """
        raise NotImplementedError()

    def get_display_name(self, subject: Subject) -> str:
        """Return the snapshot-friendly name used to identify a subject."""

        return str(subject)

    def get_type_display_name(self) -> str:
        """Return the human-readable name of this subject type."""

        return self.type

    def get_queryset(self, workspace_id: Optional[int] = None) -> Optional[QuerySet]:
        """Return subjects matching the workspace scope, if listable."""

        return None

    def get_options_queryset(
        self,
        workspace: Optional["Workspace"] = None,
        search: str = "",
        exclude_ids: Optional[List[int]] = None,
    ) -> Optional[QuerySet]:
        """Return a standardized queryset of selectable subject options."""

        return None

    def get_historical_options_queryset(
        self,
        workspace: Optional["Workspace"] = None,
        search: str = "",
        exclude_ids: Optional[List[int]] = None,
    ) -> Optional[QuerySet]:
        """Return options including subjects retained for historical records."""

        return self.get_options_queryset(
            workspace=workspace, search=search, exclude_ids=exclude_ids
        )

    def get_label(self, subject: Subject) -> str:
        """Return the label shown when this subject is presented as an option."""

        return self.get_display_name(subject)

    def get_workspace_role_uids(
        self,
        subjects: List[Subject],
        workspace: "Workspace",
        include_trash: bool = False,
    ) -> Optional[Dict[int, str]]:
        """Return direct workspace role UIDs for a batch of subjects.

        Only roles belonging to ``workspace`` may be returned. The mapping must be
        keyed by subject ID and can omit subjects that have no matching direct role.

        :param subjects: The subjects whose direct roles should be fetched together.
        :param workspace: The workspace to restrict the role lookup to.
        :param include_trash: Whether trashed subjects or memberships can be used.
        :return: A subject-ID-to-role-UID mapping, or ``None`` when direct workspace
            roles are unsupported by this subject type.
        """

        return None

    def is_workspace_role_fallback(self, role_uid: str) -> bool:
        """Return whether a direct role should defer to inherited roles.

        :param role_uid: The direct workspace role UID to inspect.
        :return: Whether permission managers should use inherited roles instead.
        """

        return False

    def are_workspace_roles_available(
        self, subjects: List[Subject], workspace: "Workspace"
    ) -> List[bool]:
        """Return whether each subject's direct workspace role is available.

        :param subjects: The subjects whose roles should be checked together.
        :param workspace: The workspace in which role availability must be checked.
        :return: Availability flags in the same order as ``subjects``.
        """

        return [True] * len(subjects)

    def is_in_workspace(
        self,
        subject: Subject,
        workspace: "Workspace",
        include_trash: bool = False,
    ) -> bool:
        """
        This function checks if a subject belongs to a workspace
        :param include_trash: Whether trashed workspace memberships should count.
        :return: If the subject belongs to the workspace
        """

        return self.are_in_workspace([subject], workspace, include_trash=include_trash)[
            0
        ]

    @abc.abstractmethod
    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: "Workspace",
        include_trash: bool = False,
    ) -> List[bool]:
        """
        This function checks if the subjects belongs to a workspace
        :param include_trash: Whether trashed workspace memberships should count.
        :return: a list of bool. For each index whether the user at the same index
            belongs to the workspace or not
        """

        pass

    @abc.abstractmethod
    def get_serializer(self, model_instance, **kwargs) -> Serializer:
        """
        This function can be used to generate different serializers based on the type
        of subject that is being serialized
        :param model_instance: instance of a subject
        :param kwargs: additional kwargs that are parsed to serializer
        :return: the correct serializer for the subject
        """

        pass

    @abc.abstractmethod
    def get_users_included_in_subject(self, subject) -> List["AbstractUser"]:
        """
        Returns a list of Users which are associated with this subject.
        And associated user is any user that receives permissions in Baserow based
        on their link to this subject.
        :param subject: The subject we are trying to find the associated users for
        :return: All the associated users
        """

        pass


class SubjectTypeRegistry(Registry[SubjectType], ModelRegistryMixin[Any, SubjectType]):
    """
    This registry holds all the different subject types used across Baserow.
    """

    name = "subject"
    does_not_exist_exception_class = SubjectTypeNotExist

    def get_serializer(self, model_instance, **kwargs) -> Serializer:
        """
        This function is used to get the correct serializer for a given subject model
        instance. A SubjectType has to implement the `get_serializer` method in order
        to be serialized.
        :param model_instance: Instance of a subject
        :param kwargs: Additional kwargs passed to the serializer
        :return: The correct subject serializer
        """

        instance_type = self.get_by_model(model_instance)
        return instance_type.get_serializer(model_instance, **kwargs)

    def get_subject(
        self, type_name: str, subject_id: int, include_trash: bool = False
    ) -> Optional[Subject]:
        """
        Returns the subject stored as a type and id pair.

        :param type_name: The subject type, for example `auth.User`.
        :param subject_id: The id of the subject.
        :param include_trash: Whether a trashed subject is returned as well, for
            subject types that can be trashed.
        :return: The subject, or None when it no longer exists or its type is not
            stored in the database.
        """

        model_class = self.get(type_name).model_class
        manager = getattr(model_class, "objects", None)
        if include_trash:
            manager = getattr(model_class, "objects_and_trash", manager)
        if manager is None:
            return None
        return manager.filter(id=subject_id).first()


subject_type_registry: SubjectTypeRegistry = SubjectTypeRegistry()
