from typing import List

from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.db import transaction
from django.db.models import Case, CharField, F, IntegerField, Q, Value, When
from django.db.models.functions import Cast
from django.db.models.signals import post_delete, post_save

from baserow.core.models import User, Workspace, WorkspaceUser
from baserow.core.operations import ListWorkspaceUsersWorkspaceOperationType
from baserow.core.registries import SubjectType
from baserow.core.types import Subject


class UserSubjectType(SubjectType):
    type = "auth.User"
    model_class = User
    is_interactive_user = True
    display_name_field = "first_name"
    lookup_fields = (*SubjectType.lookup_fields, "email")
    options_list_operation_type = ListWorkspaceUsersWorkspaceOperationType.type

    supports_persistent_subjects = True

    def register_lifecycle_signals(self):
        """Account and Profile deletion both remove the executable human identity."""
        from baserow.core.models import UserProfile

        post_save.connect(
            self._synchronize_saved_user,
            sender=self.model_class,
            dispatch_uid=f"{self.type}.sync_subject",
            weak=False,
        )
        for model in (self.model_class, UserProfile):
            post_delete.connect(
                self._retain_deleted_user_subject,
                sender=model,
                dispatch_uid=f"{self.type}.retain_subject.{model._meta.label_lower}",
                weak=False,
            )

    def _synchronize_saved_user(
        self, sender, instance, raw, using, update_fields, **kwargs
    ):
        """Skip fixture loading and updates that cannot change cached attribution."""
        if raw or (
            update_fields is not None
            and not {"first_name", "email"} & set(update_fields)
        ):
            return
        self.synchronize_persistent_subject(instance, using=using)

    def _retain_deleted_user_subject(self, sender, instance, using, **kwargs):
        subject_id = instance.pk if sender is self.model_class else instance.subject_id
        self.retain_persistent_subject(subject_id, using=using)

    def synchronize_persistent_subject(self, actor, *, using="default"):
        """Read authoritative persisted values while serializing concurrent edits."""
        with transaction.atomic(using=using):
            user = (
                User.objects.using(using)
                .select_for_update(no_key=True)
                .get(pk=actor.pk)
            )
            self.synchronize_persistent_subjects([user], using=using)

    def synchronize_persistent_subjects(self, actors, *, using="default"):
        """Batch attribution for persisted Users; callers own the actor transaction."""
        from baserow.core.models import Subject as PersistentSubject

        subjects = [
            PersistentSubject(
                id=user.pk,
                type=self.type,
                name=user.first_name,
                uid=user.email,
                state="live",
            )
            for user in actors
        ]
        if (
            PersistentSubject.objects.using(using)
            .filter(pk__in=[subject.pk for subject in subjects])
            .exclude(type=self.type)
            .exists()
        ):
            raise ValueError("User Subject ID belongs to another identity type.")
        PersistentSubject.objects.using(using).bulk_create(
            subjects,
            update_conflicts=True,
            unique_fields=["id"],
            update_fields=["name", "uid", "state"],
        )

    def get_persistent_subject_workspace_filter(self, workspace_id, *, selectable=True):
        """Scope cached human identities using the existing membership rules."""
        query = Q(user_profile__user__workspaceuser__workspace_id=workspace_id)
        if selectable:
            query &= Q(
                user_profile__user__workspaceuser__workspace__trashed=False,
                user_profile__user__is_active=True,
                user_profile__to_be_deleted=False,
            )
        return query

    def has_invalid_persistent_subjects(self):
        """Verify human ID equality, linkage and authoritative cached values."""
        return User.objects.filter(
            Q(profile__subject_id__isnull=True)
            | ~Q(profile__subject_id=F("id"))
            | ~Q(profile__subject__name=F("first_name"))
            | ~Q(profile__subject__uid=F("email"))
            | ~Q(profile__subject__type=self.type)
            | ~Q(profile__subject__state="live")
        ).exists()

    def get_legacy_persistent_subject_uid(self, value):
        return value if isinstance(value, str) else None

    def get_persistent_subject_export_value(self, subject, *, include_name=True):
        if not include_name:
            return subject.uid
        return super().get_persistent_subject_export_value(subject)

    def _get_persistent_subject(self, actor):
        return actor.profile.subject

    def resolve_persistent_subject(self, subject):
        return User.objects.filter(
            profile__subject=subject, is_active=True, profile__to_be_deleted=False
        ).first()

    has_direct_workspace_roles = True

    def get_workspace_subjects(self, workspace: Workspace, include_trash=False):
        manager = (
            WorkspaceUser.objects_and_trash if include_trash else WorkspaceUser.objects
        )
        return [
            membership.user
            for membership in manager.filter(workspace=workspace).select_related("user")
        ]

    def set_workspace_role_uid(
        self,
        subject: AbstractUser,
        workspace: Workspace,
        role_uid: str,
        send_signals: bool = True,
    ):
        """Store workspace roles on membership records, retaining basic role names."""
        from baserow.core.handler import CoreHandler

        # Keep roles on WorkspaceUser.permissions so switching permission managers
        # does not lose or duplicate information. Basic permissions call BUILDER MEMBER.
        workspace_user = workspace.get_workspace_user(subject)
        permissions = "MEMBER" if role_uid == "BUILDER" else role_uid
        CoreHandler().force_update_workspace_user(
            None, workspace_user, permissions=permissions
        )

    def get_type_display_name(self):
        return "User"

    def get_display_name(self, subject: AbstractUser) -> str:
        return subject.first_name

    def get_queryset(self, workspace_id=None):
        queryset = User.objects.all()
        if workspace_id is not None:
            queryset = queryset.filter(workspaceuser__workspace_id=workspace_id)
        return queryset.order_by("email")

    def get_label(self, subject: AbstractUser) -> str:
        return subject.email

    def get_options_queryset(
        self,
        workspace: Workspace | None = None,
        search: str = "",
        exclude_ids: List[int] | None = None,
        include_inactive_and_scheduled_for_deletion: bool = False,
    ):
        """Return searchable user options, optionally scoped to a workspace."""

        queryset = User.objects.exclude(id__in=exclude_ids or [])
        if not include_inactive_and_scheduled_for_deletion:
            queryset = queryset.filter(is_active=True, profile__to_be_deleted=False)
        if workspace is not None:
            queryset = queryset.filter(workspaceuser__workspace=workspace)
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(username__icontains=search)
                | Q(email__icontains=search)
            )
        return queryset.annotate(
            subject_id=F("id"),
            subject_type=Value(self.type, output_field=CharField()),
            subject_name=Case(
                When(first_name="", then=F("email")),
                default=F("first_name"),
                output_field=CharField(),
            ),
            subject_label=F("email"),
            subject_email=F("email"),
            subject_count=Cast(Value(None), output_field=IntegerField()),
        ).values(
            "subject_id",
            "subject_type",
            "subject_name",
            "subject_label",
            "subject_email",
            "subject_count",
        )

    def get_historical_options_queryset(
        self,
        workspace: Workspace | None = None,
        search: str = "",
        exclude_ids: List[int] | None = None,
    ):
        """Return users retained for historical records after access is removed."""

        return self.get_options_queryset(
            workspace=workspace,
            search=search,
            exclude_ids=exclude_ids,
            include_inactive_and_scheduled_for_deletion=True,
        )

    def get_workspace_role_uids(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> dict[int, str]:
        """Return workspace membership permissions keyed by User ID."""

        workspace_user_manager = (
            WorkspaceUser.objects_and_trash if include_trash else WorkspaceUser.objects
        )
        return dict(
            workspace_user_manager.filter(
                workspace=workspace,
                user_id__in=[subject.id for subject in subjects],
            ).values_list("user_id", "permissions")
        )

    def is_workspace_role_fallback(self, role_uid: str) -> bool:
        return role_uid == getattr(
            settings, "NO_ROLE_LOW_PRIORITY_UID", "NO_ROLE_LOW_PRIORITY"
        )

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        """
        Check whether the given subjects ar member of the given workspace.
        """

        prefetched = getattr(workspace, "_prefetched_objects_cache", {})
        if not include_trash and "workspaceuser_set" in prefetched:
            user_ids_in_workspace = {
                workspace_user.user_id
                for workspace_user in workspace.workspaceuser_set.all()
            }
            missing_subjects = [
                subject
                for subject in subjects
                if subject.id not in user_ids_in_workspace
            ]
            if missing_subjects:
                user_ids_in_workspace.update(
                    WorkspaceUser.objects.filter(
                        user__in=missing_subjects,
                        workspace=workspace,
                        user__profile__to_be_deleted=False,
                        user__is_active=True,
                    ).values_list("user_id", flat=True)
                )
            return [
                subject.id in user_ids_in_workspace
                and subject.is_active
                and not subject.profile.to_be_deleted
                for subject in subjects
            ]

        workspace_user_manager = (
            WorkspaceUser.objects_and_trash if include_trash else WorkspaceUser.objects
        )
        user_ids_in_workspace = set(
            workspace_user_manager.filter(
                user__in=subjects,
                workspace=workspace,
                user__profile__to_be_deleted=False,
                user__is_active=True,
            ).values_list("user_id", flat=True)
        )

        return [s.id in user_ids_in_workspace for s in subjects]

    def get_serializer(self, model_instance, **kwargs):
        from baserow.api.user.serializers import SubjectUserSerializer

        return SubjectUserSerializer(model_instance, **kwargs)

    def get_users_included_in_subject(
        self, subject: AbstractUser
    ) -> List[AbstractUser]:
        return [subject]


class AnonymousUserSubjectType(SubjectType):
    type = "anonymous"
    model_class = AnonymousUser

    def get_type_display_name(self):
        return "Anonymous user"

    def get_display_name(self, subject: AnonymousUser) -> str:
        # Row history persists this as a stable fallback. Clients translate the
        # anonymous actor label at render time so it uses the viewer's language.
        return "Anonymous User"

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        """
        Anonymous users are never member of any workspace.
        """

        return [False for _ in subjects]

    def get_serializer(self, model_instance, **kwargs):
        return None

    def get_users_included_in_subject(
        self, subject: AnonymousUser
    ) -> List[AbstractUser]:
        return []
